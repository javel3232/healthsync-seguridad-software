# AI Agent Marketplace
Un inversor te contrata para desarrollar un marketplace donde empresas y desarrolladores publican, compran y ejecutan agentes de inteligencia artificial especializados.

## Registro y verificación de cuentas (20%)
Los usuarios se registran con nombre, correo, contraseña y tipo de cuenta (desarrollador o empresa). Las cuentas quedan inactivas hasta que un administrador aprueba la solicitud revisando el perfil del solicitante.
- Los administradores gestionan las solicitudes de activación desde un panel de control. Una vez aprobadas, el usuario recibe un correo de bienvenida con sus credenciales de acceso a la API.
- Programa de referidos: los usuarios activos obtienen un código de referido. Cuando un nuevo usuario se registra con ese código y es aprobado, el referidor recibe 5 USD de crédito en la plataforma.
- Bot de aprobación automática: simule un administrador que periódicamente (cada minuto) aprueba solicitudes de registro cuyo perfil cumpla con criterios básicos de completitud [C++]. Una vez aprobados, el usuario recibe un correo.

## Catálogo de agentes (10%)
Los desarrolladores pueden publicar agentes de IA en el catálogo, especificando nombre, descripción, precio por ejecución (en USD), categoría y un endpoint de prueba. Los administradores aprueban o rechazan la publicación de cada agente antes de que sea visible en el catálogo.

## Ejecución de agentes (30%)
Usando la API key generada al activar la cuenta, los usuarios pueden invocar agentes del catálogo. Cada ejecución descuenta el costo correspondiente del saldo del usuario y registra la transacción.
- La plataforma consume la API pública de OpenRouter (https://openrouter.ai/api/v1) para enrutar las invocaciones hacia el modelo de lenguaje que cada agente declara usar.
- Historial de ejecuciones: los usuarios pueden consultar el registro de todas sus invocaciones, incluyendo agente usado, costo, timestamp y resultado resumido.

## Ejecuciones programadas (30%)
Los usuarios pueden programar la ejecución recurrente de un agente (por ejemplo: cada hora, cada día) o condicional (cuando el saldo disponible supere un umbral). La programación incluye el prompt de entrada y los parámetros de activación.
- Robot de despacho: un robot que se ejecuta periódicamente (cada segundo) revisa las ejecuciones programadas y las lanza cuando se cumple la condición definida [C++].

## Transferencias de crédito (10%)
Los usuarios pueden transferir saldo de crédito a otros usuarios registrados en la plataforma.
