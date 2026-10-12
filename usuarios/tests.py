from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Proyecto


def gestion(prefijo, total):
    return {
        f'{prefijo}-TOTAL_FORMS': str(total),
        f'{prefijo}-INITIAL_FORMS': '0',
        f'{prefijo}-MIN_NUM_FORMS': '0',
        f'{prefijo}-MAX_NUM_FORMS': '1000',
    }


class CrearProyectoWizardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='clave-segura-123')
        self.client.force_login(self.user)
        self.url = reverse('crear_proyecto')

    def datos_base(self, **extra):
        datos = {
            'nombre': 'Centro comunitario',
            'categoria': 'PUBLICO',
            'fecha_inicio': '2027-01-01',
            'fecha_fin': '2027-12-31',
            'descripcion': 'Construcción y dotación de un centro comunitario para adultos mayores.',
            'pais': 'HND',
            **gestion('actividades', 0),
            **gestion('rubros', 0),
            **gestion('riesgos_matriz', 0),
        }
        datos.update(extra)
        return datos

    def test_get_renderiza_los_seis_pasos(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        for paso in range(1, 7):
            self.assertContains(resp, f'id="step-{paso}"')
        self.assertContains(resp, 'enctype="multipart/form-data"')

    def test_guarda_proyecto_con_cronograma_presupuesto_y_riesgos(self):
        datos = self.datos_base(**{
            **gestion('actividades', 2),
            'actividades-0-tipo': 'ACTIVIDAD',
            'actividades-0-nombre': 'Diseño',
            'actividades-0-fecha_inicio': '2027-01-01',
            'actividades-0-fecha_fin': '2027-03-31',
            'actividades-1-tipo': 'HITO',
            'actividades-1-nombre': 'Entrega de obra',
            'actividades-1-fecha_inicio': '2027-12-01',
            'actividades-1-fecha_fin': '2027-12-01',
            **gestion('rubros', 3),
            'rubros-0-rubro': 'INFRA', 'rubros-0-fuente': 'PUBLICO', 'rubros-0-monto': '1000.50',
            'rubros-1-rubro': 'TALENTO', 'rubros-1-fuente': 'COOPERACION', 'rubros-1-monto': '500',
            # Fila eliminada en el navegador: no debe guardarse ni sumar
            'rubros-2-rubro': 'OTRO', 'rubros-2-fuente': 'PRIVADO', 'rubros-2-monto': '999', 'rubros-2-DELETE': 'on',
            **gestion('riesgos_matriz', 1),
            'riesgos_matriz-0-descripcion': 'Retraso en desembolsos',
            'riesgos_matriz-0-tipo': 'FINANCIERO',
            'riesgos_matriz-0-probabilidad': '3',
            'riesgos_matriz-0-impacto': '3',
        })
        datos['archivo_nac'] = SimpleUploadedFile('plan.pdf', b'%PDF-1.4', content_type='application/pdf')
        resp = self.client.post(self.url, datos)
        self.assertRedirects(resp, reverse('home'))

        proyecto = Proyecto.objects.get()
        self.assertEqual(proyecto.usuario, self.user)
        self.assertEqual(proyecto.actividades.count(), 2)
        self.assertEqual(proyecto.rubros.count(), 2)
        self.assertEqual(proyecto.presupuesto, Decimal('1500.50'))
        riesgo = proyecto.matriz_riesgos.get()
        self.assertEqual(riesgo.nivel, 9)
        self.assertEqual(str(riesgo.nivel_label), 'Alto')
        self.assertEqual(proyecto.documentos.count(), 1)

    def test_actividad_fuera_del_rango_reabre_paso_3(self):
        datos = self.datos_base(**{
            **gestion('actividades', 1),
            'actividades-0-tipo': 'ACTIVIDAD',
            'actividades-0-nombre': 'Cierre',
            'actividades-0-fecha_inicio': '2027-06-01',
            'actividades-0-fecha_fin': '2028-02-01',
        })
        resp = self.client.post(self.url, datos)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['paso_inicial'], 3)
        self.assertFalse(Proyecto.objects.exists())

    def test_fecha_fin_anterior_a_inicio_es_invalida(self):
        resp = self.client.post(self.url, self.datos_base(fecha_fin='2026-06-01'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('fecha_fin', resp.context['form'].errors)
        self.assertEqual(resp.context['paso_inicial'], 3)

    def test_rubro_con_monto_cero_reabre_paso_4(self):
        datos = self.datos_base(**{
            **gestion('rubros', 1),
            'rubros-0-rubro': 'EQUIPOS', 'rubros-0-fuente': 'PROPIOS', 'rubros-0-monto': '0',
        })
        resp = self.client.post(self.url, datos)
        self.assertEqual(resp.context['paso_inicial'], 4)
        self.assertFalse(Proyecto.objects.exists())

    def test_filas_vacias_se_ignoran(self):
        datos = self.datos_base(**{
            **gestion('actividades', 1),
            'actividades-0-tipo': 'ACTIVIDAD',
            **gestion('riesgos_matriz', 1),
            'riesgos_matriz-0-probabilidad': '2',
            'riesgos_matriz-0-impacto': '2',
        })
        resp = self.client.post(self.url, datos)
        self.assertRedirects(resp, reverse('home'))
        proyecto = Proyecto.objects.get()
        self.assertEqual(proyecto.actividades.count(), 0)
        self.assertEqual(proyecto.matriz_riesgos.count(), 0)
        self.assertIsNone(proyecto.presupuesto)
