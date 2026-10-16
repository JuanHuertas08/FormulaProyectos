from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import diagnostico
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

    def test_guardar_proyecto_final_queda_completo(self):
        resp = self.client.post(self.url, self.datos_base(accion='finalizar', paso='6'))
        self.assertRedirects(resp, reverse('home'))
        proyecto = Proyecto.objects.get()
        self.assertEqual(proyecto.estado, Proyecto.ESTADO_COMPLETO)
        self.assertEqual(proyecto.paso_actual, 6)

    def test_guardar_avance_solo_exige_nombre_y_queda_en_proceso(self):
        datos = {
            'nombre': 'Borrador',
            'descripcion': 'corta',
            'accion': 'borrador',
            'paso': '2',
            **gestion('actividades', 0),
            **gestion('rubros', 0),
            **gestion('riesgos_matriz', 0),
        }
        resp = self.client.post(self.url, datos)
        proyecto = Proyecto.objects.get()
        self.assertRedirects(resp, reverse('editar_proyecto', args=[proyecto.pk]) + '?paso=2')
        self.assertEqual(proyecto.estado, Proyecto.ESTADO_EN_PROCESO)
        self.assertEqual(proyecto.paso_actual, 2)
        self.assertIsNone(proyecto.fecha_inicio)

    def test_guardar_avance_sin_nombre_falla(self):
        datos = self.datos_base(nombre='', accion='borrador', paso='3')
        resp = self.client.post(self.url, datos)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['paso_inicial'], 1)
        self.assertFalse(Proyecto.objects.exists())

    def test_finalizar_exige_campos_del_paso_1(self):
        datos = self.datos_base(descripcion='corta', accion='finalizar')
        resp = self.client.post(self.url, datos)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('descripcion', resp.context['form'].errors)
        self.assertEqual(resp.context['paso_inicial'], 1)

    def test_continuar_borrador_y_finalizar_conserva_filas(self):
        proyecto = Proyecto.objects.create(usuario=self.user, nombre='Borrador', paso_actual=4)
        rubro = proyecto.rubros.create(rubro='INFRA', fuente='PUBLICO', monto=Decimal('100'))
        url = reverse('editar_proyecto', args=[proyecto.pk])

        resp = self.client.get(url)
        self.assertEqual(resp.context['paso_inicial'], 4)
        self.assertContains(resp, 'name="rubros-0-id"')

        # La fila existente se reenvía sin cambios y se agrega una nueva
        datos = self.datos_base(**{
            'rubros-TOTAL_FORMS': '2', 'rubros-INITIAL_FORMS': '1',
            'rubros-MIN_NUM_FORMS': '0', 'rubros-MAX_NUM_FORMS': '1000',
            'rubros-0-id': str(rubro.pk), 'rubros-0-rubro': 'INFRA',
            'rubros-0-fuente': 'PUBLICO', 'rubros-0-monto': '100.00',
            'rubros-1-rubro': 'TALENTO', 'rubros-1-fuente': 'PROPIOS', 'rubros-1-monto': '50',
            'accion': 'finalizar',
        })
        resp = self.client.post(url, datos)
        self.assertRedirects(resp, reverse('home'))
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.estado, Proyecto.ESTADO_COMPLETO)
        self.assertEqual(proyecto.rubros.count(), 2)
        self.assertEqual(proyecto.presupuesto, Decimal('150.00'))
        self.assertEqual(Proyecto.objects.count(), 1)

    def test_no_se_puede_editar_proyecto_de_otro_usuario(self):
        otro = User.objects.create_user('beto', password='clave-segura-456')
        ajeno = Proyecto.objects.create(usuario=otro, nombre='Ajeno')
        resp = self.client.get(reverse('editar_proyecto', args=[ajeno.pk]))
        self.assertEqual(resp.status_code, 404)

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


def respuesta_api(texto, urls_buscador=(), stop_reason='end_turn', error_busqueda=None):
    """Simula la respuesta de messages.create con un bloque de búsqueda web y uno de texto."""
    resultado_busqueda = (
        SimpleNamespace(type='web_search_tool_result_error', error_code=error_busqueda)
        if error_busqueda else [SimpleNamespace(url=u) for u in urls_buscador]
    )
    contenido = [
        SimpleNamespace(type='server_tool_use'),
        SimpleNamespace(type='web_search_tool_result', content=resultado_busqueda),
    ]
    if texto is not None:
        contenido.append(SimpleNamespace(type='text', text=texto))
    return SimpleNamespace(content=contenido, stop_reason=stop_reason, _request_id='req_prueba')


@override_settings(ANTHROPIC_API_KEY='clave-de-prueba')
class GenerarDiagnosticoTests(TestCase):
    def llamar(self, texto, urls=(), respuestas=None, **kwargs):
        """Ejecuta generar_diagnostico con la API simulada. Devuelve el resultado
        y los kwargs de la última llamada a la API."""
        with mock.patch('anthropic.Anthropic') as cliente:
            create = cliente.return_value.with_options.return_value.beta.messages.create
            create.side_effect = respuestas or [respuesta_api(texto, urls)]
            resultado = diagnostico.generar_diagnostico(
                pais='HND', categoria='Público', nombre='Centro',
                descripcion='Centro para adultos mayores en Choluteca', **kwargs,
            )
            self.create = create
            return resultado, create.call_args.kwargs

    def test_incluye_contexto_y_fuentes_ampliadas(self):
        _, llamada = self.llamar(
            '{"cifras": "a", "antecedentes": "b", "necesidades": "c", "fuentes": []}',
            contexto={'ods': ['3. Salud y bienestar'], 'articulacion_municipal': 'Plan Choluteca 2026', 'leyes': []},
        )
        prompt = llamada['messages'][0]['content']
        self.assertIn('3. Salud y bienestar', prompt)
        self.assertIn('Plan Choluteca 2026', prompt)
        self.assertNotIn('Marco legal seleccionado', prompt)  # vacío: no se envía
        dominios = llamada['tools'][0]['allowed_domains']
        for dominio in ('ine.gob.hn', 'salud.gob.hn', 'worldbank.org', 'iadb.org', 'cepal.org'):
            self.assertIn(dominio, dominios)
        self.assertEqual(llamada['tools'][0]['max_uses'], diagnostico.MAX_BUSQUEDAS_COMPLETO)

    def test_busqueda_por_seccion_devuelve_solo_esa_seccion(self):
        resultado, llamada = self.llamar('{"cifras": "Dato 2024 (INE)", "fuentes": ["https://ine.gob.hn/x"]}', seccion='cifras')
        self.assertEqual(resultado, {
            'cifras': 'Dato 2024 (INE)', 'fuentes': ['https://ine.gob.hn/x'],
            'observaciones': '', 'secciones_vacias': [],
        })
        self.assertEqual(llamada['tools'][0]['max_uses'], diagnostico.MAX_BUSQUEDAS_SECCION)
        self.assertIn('UNA sola sección', llamada['messages'][0]['content'])

    def test_extrae_json_aunque_haya_texto_alrededor(self):
        texto = (
            'Busqué en el INE.\n```json\n'
            '{"cifras": "x", "antecedentes": "y", "necesidades": "z", "fuentes": []}\n```'
        )
        resultado, _ = self.llamar(texto)
        self.assertEqual(resultado['necesidades'], 'z')

    def test_sin_fuentes_citadas_usa_las_del_buscador(self):
        urls = [f'https://ine.gob.hn/{i}' for i in range(15)]
        resultado, _ = self.llamar('{"cifras": "x", "antecedentes": "y", "necesidades": "z"}', urls)
        self.assertEqual(resultado['fuentes'], urls[:diagnostico.MAX_FUENTES_RESPALDO])

    def test_usa_modelo_actual_con_fallback_y_tokens_suficientes(self):
        _, llamada = self.llamar('{"cifras": "a", "antecedentes": "b", "necesidades": "c"}')
        self.assertEqual(llamada['model'], 'claude-opus-5-5')
        self.assertEqual(llamada['fallbacks'], 'default')
        self.assertIn('server-side-fallback-2026-07-01', llamada['betas'])
        self.assertGreaterEqual(llamada['max_tokens'], 16000)

    def test_reanuda_pause_turn(self):
        pausada = respuesta_api(None, ['https://ine.gob.hn/1'], stop_reason='pause_turn')
        final = respuesta_api('{"cifras": "a", "antecedentes": "b", "necesidades": "c", "fuentes": []}')
        resultado, llamada = self.llamar(None, respuestas=[pausada, final])
        self.assertEqual(self.create.call_count, 2)
        # La continuación reenvía el turno pausado como mensaje del asistente
        self.assertEqual(llamada['messages'][1]['role'], 'assistant')
        self.assertEqual(llamada['messages'][1]['content'], pausada.content)
        self.assertEqual(resultado['cifras'], 'a')

    def test_pause_turn_sin_terminar_da_error_controlado(self):
        pausadas = [respuesta_api(None, stop_reason='pause_turn')] * (diagnostico.MAX_CONTINUACIONES + 1)
        with self.assertRaisesMessage(diagnostico.DiagnosticoError, 'no alcanzó a terminar'):
            self.llamar(None, respuestas=pausadas)

    def test_secciones_vacias_y_observaciones(self):
        resultado, _ = self.llamar(
            '{"cifras": "", "antecedentes": "Dato", "necesidades": "  ", "fuentes": ["https://ine.gob.hn/a"], '
            '"observaciones": "No hay series municipales publicadas."}'
        )
        self.assertEqual(resultado['secciones_vacias'], ['cifras', 'necesidades'])
        self.assertEqual(resultado['observaciones'], 'No hay series municipales publicadas.')
        self.assertEqual(resultado['fuentes'], ['https://ine.gob.hn/a'])

    def test_sin_resultados_por_error_de_busqueda(self):
        resultado, _ = self.llamar(
            '{"cifras": "", "antecedentes": "", "necesidades": ""}',
            respuestas=[respuesta_api('{"cifras": "", "antecedentes": "", "necesidades": ""}', error_busqueda='unavailable')],
        )
        self.assertEqual(resultado['secciones_vacias'], ['cifras', 'antecedentes', 'necesidades'])
        self.assertIn('no pudo consultar', resultado['observaciones'])
        self.assertEqual(resultado['fuentes'], [])

    def test_el_salvador_usa_bcr_en_vez_de_digestyc(self):
        self.assertIn('bcr.gob.sv', diagnostico.FUENTES_POR_PAIS['SLV'])
        self.assertNotIn('digestyc.gob.sv', diagnostico.FUENTES_POR_PAIS['SLV'])


class BuscarDiagnosticoVistaTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user('ana', password='clave-segura-123'))
        self.url = reverse('buscar_diagnostico')

    def test_envia_contexto_y_seccion(self):
        with mock.patch('usuarios.views.generar_diagnostico', return_value={'cifras': 'x', 'fuentes': []}) as gen:
            resp = self.client.post(self.url, {
                'pais': 'COL', 'categoria': 'PUBLICO', 'nombre': 'Centro', 'descripcion': 'Desc',
                'ods': ['3', '99'], 'leyes': ['Ley 100 de 1993'], 'articulacion_regional': 'Plan Cundinamarca',
                'seccion': 'cifras',
            })
        self.assertEqual(resp.status_code, 200)
        kwargs = gen.call_args.kwargs
        self.assertEqual(kwargs['seccion'], 'cifras')
        self.assertEqual(kwargs['categoria'], 'Público')
        self.assertEqual(kwargs['contexto']['ods'], ['ODS 3: Salud y bienestar'])  # código inválido descartado
        self.assertEqual(kwargs['contexto']['leyes'], ['Ley 100 de 1993'])
        self.assertEqual(kwargs['contexto']['articulacion_regional'], 'Plan Cundinamarca')

    def test_seccion_invalida(self):
        resp = self.client.post(self.url, {'pais': 'COL', 'nombre': 'C', 'descripcion': 'D', 'seccion': 'otra'})
        self.assertEqual(resp.status_code, 400)


class ResumenBusquedasTests(TestCase):
    def test_resume_consultas_resultados_y_errores(self):
        contenido = [
            SimpleNamespace(type='server_tool_use', id='a', input={'query': 'adultos mayores Choluteca'}),
            SimpleNamespace(type='web_search_tool_result', tool_use_id='a', content=[
                SimpleNamespace(url='https://www.ine.gob.hn/x'), SimpleNamespace(url='https://www.ine.gob.hn/y'),
            ]),
            SimpleNamespace(type='server_tool_use', id='b', input={'query': 'pobreza Honduras'}),
            SimpleNamespace(type='web_search_tool_result', tool_use_id='b',
                            content=SimpleNamespace(type='web_search_tool_result_error', error_code='unavailable')),
        ]
        self.assertEqual(diagnostico.resumen_busquedas(contenido), [
            "búsqueda \"adultos mayores Choluteca\": 2 resultados ['www.ine.gob.hn']",
            'búsqueda "pobreza Honduras": ERROR unavailable',
        ])

    def test_sin_busquedas(self):
        self.assertEqual(diagnostico.resumen_busquedas([]), ['la IA no hizo ninguna búsqueda web'])


@override_settings(ANTHROPIC_API_KEY='clave-de-prueba')
class ProbarDiagnosticoComandoTests(TestCase):
    def test_sin_restriccion_omite_allowed_domains_y_muestra_detalle(self):
        from io import StringIO
        from django.core.management import call_command

        salida = StringIO()
        with mock.patch('anthropic.Anthropic') as cliente:
            create = cliente.return_value.with_options.return_value.beta.messages.create
            create.return_value = respuesta_api('{"cifras": "Dato", "antecedentes": "", "necesidades": "x"}')
            call_command('probar_diagnostico', pais='HND', descripcion='Centro', sin_restriccion=True, stdout=salida)
        self.assertNotIn('allowed_domains', create.call_args.kwargs['tools'][0])
        texto = salida.getvalue()
        self.assertIn('toda la web', texto)
        self.assertIn('antecedentes: VACÍA', texto)


@override_settings(ANTHROPIC_API_KEY='clave-de-prueba')
class CredencialInvalidaTests(TestCase):
    def test_401_da_mensaje_de_configuracion(self):
        import anthropic
        import httpx2

        respuesta = httpx2.Response(401, request=httpx2.Request('POST', 'https://api.anthropic.com/v1/messages'))
        error = anthropic.AuthenticationError('invalid x-api-key', response=respuesta, body=None)
        with mock.patch('anthropic.Anthropic') as cliente:
            cliente.return_value.with_options.return_value.beta.messages.create.side_effect = error
            with self.assertRaisesMessage(diagnostico.DiagnosticoError, 'credencial inválida'):
                diagnostico.generar_diagnostico(pais='HND', categoria='', nombre='C', descripcion='D')


class CorreoBienvenidaTests(TestCase):
    datos = {
        'username': 'nuevo', 'nombres': 'Ana', 'apellidos': 'Pérez',
        'email': 'ana@example.com', 'confirmar_email': 'ana@example.com',
        'telefono': '+504 9999-9999', 'fecha_nacimiento': '1990-01-01',
        'pais': 'Honduras', 'ciudad': 'Tegucigalpa',
        'password': 'Clave-Segura-123', 'confirmar_password': 'Clave-Segura-123',
    }

    def test_registro_envia_bienvenida(self):
        from django.core import mail

        resp = self.client.post(reverse('register'), self.datos)
        self.assertRedirects(resp, reverse('login'))
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['ana@example.com'])
        self.assertEqual(correo.subject, 'Bienvenido a InvestProject')
        self.assertIn('Hola Ana', correo.body)
        self.assertIn('http://testserver/usuarios/login/', correo.body)
        html = correo.alternatives[0][0]
        self.assertIn('Ingresar a InvestProject', html)

    def test_bienvenida_en_ingles(self):
        from django.core import mail

        self.client.post(reverse('register'), self.datos, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(mail.outbox[0].subject, 'Welcome to InvestProject')

    def test_si_falla_el_envio_la_cuenta_se_crea_igual(self):
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ConnectionError('Brevo caído')):
            resp = self.client.post(reverse('register'), self.datos)
        self.assertRedirects(resp, reverse('login'))
        self.assertTrue(User.objects.filter(username='nuevo').exists())


class ValidarUsuarioTests(TestCase):
    def setUp(self):
        User.objects.create_user('ana.perez', password='clave-segura-123')
        self.url = reverse('validar_usuario')

    def consultar(self, valor):
        return self.client.get(self.url, {'username': valor}).json()

    def test_disponible(self):
        self.assertEqual(self.consultar('juan_2026')['disponible'], True)

    def test_en_uso_sin_distinguir_mayusculas(self):
        respuesta = self.consultar('Ana.Perez')
        self.assertFalse(respuesta['disponible'])
        self.assertIn('ya está en uso', respuesta['mensaje'])

    def test_formato_invalido(self):
        respuesta = self.consultar('ana perez')
        self.assertFalse(respuesta['disponible'])
        self.assertIn('sin espacios', respuesta['mensaje'])

    def test_vacio(self):
        self.assertFalse(self.consultar('')['disponible'])

    def test_registro_rechaza_duplicado_con_otras_mayusculas(self):
        datos = dict(CorreoBienvenidaTests.datos, username='ANA.PEREZ')
        resp = self.client.post(reverse('register'), datos)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('username', resp.context['form'].errors)
        self.assertEqual(User.objects.filter(username__iexact='ana.perez').count(), 1)


class CorreoUnicoTests(TestCase):
    def setUp(self):
        User.objects.create_user('existente', email='ana@example.com', password='clave-segura-123')

    def test_rechaza_correo_registrado_sin_distinguir_mayusculas(self):
        datos = dict(CorreoBienvenidaTests.datos, username='otra.ana',
                     email='ANA@Example.com', confirmar_email='ANA@Example.com')
        resp = self.client.post(reverse('register'), datos)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Ya existe una cuenta registrada con este correo', resp.context['form'].errors['email'][0])
        self.assertFalse(User.objects.filter(username='otra.ana').exists())

    def test_acepta_correo_nuevo(self):
        datos = dict(CorreoBienvenidaTests.datos, username='otra.ana',
                     email='otra@example.com', confirmar_email='otra@example.com')
        resp = self.client.post(reverse('register'), datos)
        self.assertRedirects(resp, reverse('login'))
