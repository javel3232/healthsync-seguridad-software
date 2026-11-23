# HealthSync
Un inversor te contrata para desarrollar una plataforma de salud digital que integra datos de dispositivos wearables, permite la consulta con profesionales de salud y gestiona registros médicos personales.

## Registro y verificación de usuarios (20%)
Los usuarios se registran con nombre, correo, contraseña, fecha de nacimiento y tipo de cuenta (paciente o profesional de salud). Los profesionales deben adjuntar foto de su tarjeta profesional; su cuenta queda inactiva hasta que un administrador valide sus credenciales.
- Los administradores gestionan las solicitudes de activación de profesionales desde un panel de control. Una vez aprobadas, el profesional recibe un correo y queda visible en el directorio de la plataforma.
- Programa de referidos: los usuarios activos obtienen un código que pueden compartir. Cuando un nuevo usuario completa su registro usando el código, el referidor acumula puntos canjeables por meses de suscripción premium.
- Bot de validación de profesionales: simule un administrador que periódicamente (cada minuto) valida las solicitudes de registro de profesionales de salud cuya documentación esté completa [C++]. Una vez validados, reciben un correo de activación.

## Sincronización de dispositivos wearables (10%)
Los pacientes pueden vincular su cuenta con dispositivos wearables. La plataforma consume la API pública de Open mHealth (https://www.openmhealth.org/documentation) para normalizar e importar métricas como frecuencia cardíaca, pasos diarios, nivel de oxígeno en sangre y horas de sueño. Los datos importados quedan almacenados en el perfil de salud del paciente.

## Consultas médicas virtuales (30%)
Los pacientes pueden agendar y realizar consultas con profesionales de salud disponibles en el directorio. Cada consulta tiene un costo en créditos que se descuenta del saldo del paciente al momento de confirmar la cita.
- Durante la consulta, el profesional puede acceder al historial de métricas del wearable del paciente (con su consentimiento explícito) y registrar notas clínicas.
- Historial de consultas: tanto pacientes como profesionales pueden consultar el registro de todas sus citas, incluyendo fecha, diagnóstico resumido, notas clínicas y costo.

## Alertas de salud programadas (30%)
Los pacientes pueden configurar alertas personalizadas que se activan cuando una métrica del wearable supera o cae por debajo de un umbral definido (por ejemplo: frecuencia cardíaca mayor a 120 bpm). Al activarse, la plataforma notifica al paciente por correo y, si el paciente lo autorizó, alerta también a un profesional de salud vinculado.
- Robot de monitoreo: un robot que se ejecuta periódicamente (cada segundo) evalúa las métricas más recientes de cada paciente activo contra sus umbrales configurados y dispara las notificaciones correspondientes [C++].

## Transferencias de crédito (10%)
Los usuarios pueden transferir saldo de crédito a otros usuarios registrados en la plataforma, por ejemplo para que un familiar pague las consultas de otro paciente.
