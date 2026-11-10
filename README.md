# Panther iOS — servidor de licencias y catálogo

Backend independiente para Render. **No modifica ni compila la aplicación iOS.**

## Publicación
1. Crea un repositorio **privado** en GitHub y sube el contenido de esta carpeta a la raíz.
2. En Render selecciona New > Blueprint y conecta el repositorio; Render leerá `render.yaml`.
3. Introduce `TELEGRAM_BOT_TOKEN` como variable secreta de Render. Nunca lo subas a GitHub.
4. Espera a que `/health` responda `{"ok":true}`.
5. En Render copia el valor de `TELEGRAM_WEBHOOK_SECRET` y la URL pública del servicio.
6. Desde tu equipo, registra el webhook con una solicitud POST a `https://api.telegram.org/bot<TU_TOKEN>/setWebhook`, con los campos `url=https://TU_SERVICIO.onrender.com/telegram/webhook` y `secret_token=EL_SECRETO_DE_RENDER`. No pegues el token en chats ni en repositorios.
7. Envía `/generar 30` a @Key_delete_bot desde la cuenta Telegram con ID 8449818228.

## Comandos
- `/generar 30`: genera key de 30 días (1–100).
- `/keys`: lista fechas y activaciones sin revelar keys.
- `/revocar panther-12345678`: revoca una key.
- `/patch Nombre https://servidor.example/archivo`: agrega una referencia al catálogo.
- `/patches`: lista los patches.
- `/quitar 1`: elimina un patch del catálogo.

## API de la app
`POST /v1/activate` con JSON `{"key":"panther-12345678","device_id":"identificador-aleatorio-persistente-del-dispositivo"}`.
`POST /v1/patches` con el mismo cuerpo devuelve el catálogo. **No ejecuta ni instala archivos.**

## Limitaciones importantes
- El código iOS aún debe integrar las llamadas HTTPS, la pantalla de acceso y las restricciones de navegación. No está conectado automáticamente.
- El dispositivo queda asociado al primer identificador presentado; la app debe conservarlo de forma segura (p. ej., Keychain). No es una prueba de identidad de hardware infalsificable.
- Este ejemplo usa SQLite con disco persistente de Render en plan compatible; no es PostgreSQL ni funciona correctamente en despliegues sin disco persistente.
- El acceso de administrador `Naruto00` **no se implementa aquí**: una contraseña fija en una app distribuida no es segura. Debe diseñarse autenticación de administrador en el servidor.
- La caducidad se comprueba en cada petición. El catálogo contiene enlaces, no código ejecutable.
- La aplicación IPA necesita compilación y firma por separado.
