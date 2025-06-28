import logging
import asyncio
import signal
import re
import os  # <-- AÑADE ESTA LÍNEA
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import notion_client

# ==============================================================================
# --- CONFIGURACIÓN (AHORA USA VARIABLES DE ENTORNO) ---
# ==============================================================================
# El código ahora leerá las claves de un lugar seguro en el servidor.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
NOTION_KEY = os.environ.get("NOTION_KEY")
DATABASE_ID = os.environ.get("DATABASE_ID")

# Configuración del logging para ver mensajes de estado en la terminal
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializa el cliente de Notion con tu llave
notion = notion_client.Client(auth=NOTION_KEY)

async def add_to_notion(content: str):
    """Detecta si el contenido es una URL y lo añade a la base de datos de Notion."""
    
    # Expresión regular para encontrar la primera URL en el texto
    url_pattern = r'https?://[^\s]+'
    found_urls = re.findall(url_pattern, content)
    
    properties = {}
    
    # Si encontramos una URL, la usamos en la propiedad 'URL' y el texto completo en el 'Nombre'
    if found_urls:
        properties["URL"] = {"url": found_urls[0]}
        properties["Nombre"] = {"title": [{"text": {"content": content}}]}
    else:
        # Si no hay URL, solo usamos el texto en el 'Nombre'
        properties["Nombre"] = {"title": [{"text": {"content": content}}]}

    try:
        # Llama a la API de Notion para crear una nueva página (una nueva fila)
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties
        )
        logger.info(f"Éxito: Contenido '{content[:30]}...' añadido a Notion.")
        return True
    except Exception as e:
        logger.error(f"Error al añadir a Notion: {e}")
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Función para el comando /start."""
    await update.message.reply_text('¡Hola! Soy tu bot de buzón para Notion. Envíame cualquier texto o enlace y lo guardaré por ti.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja cualquier mensaje de texto que no sea un comando."""
    message_text = update.message.text
    
    # Llama a la función que guarda en Notion
    success = await add_to_notion(content=message_text)
    
    # Responde al usuario en Telegram
    if success:
        await update.message.reply_text('✅ ¡Guardado en Notion!')
    else:
        await update.message.reply_text('❌ ¡Ups! Hubo un error al conectar con Notion.')

import asyncio
import signal

async def main() -> None:
    """
    Función principal que configura e inicia el bot de forma manual y robusta.
    """
    
    # Crea un "evento" de asyncio. Es como una señal que le diremos cuándo parar.
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        """Manejador para detener el bot con Ctrl+C."""
        logger.info("¡Señal de detención recibida (Ctrl+C)! Cerrando...")
        shutdown_event.set()

    # Asocia la señal de Ctrl+C (SIGINT) a nuestro manejador
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Iniciando el bot (modo manual)...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    try:
        # Inicia los componentes de la aplicación por separado
        await application.initialize()
        await application.updater.start_polling()
        await application.start()
        
        logger.info("El bot está ahora escuchando mensajes... Presiona Ctrl+C para detenerlo.")
        
        # Espera hasta que el evento de cierre sea activado (por Ctrl+C)
        await shutdown_event.wait()
        
    except Exception as e:
        logger.error(f"Ocurrió un error inesperado: {e}")
    finally:
        logger.info("Iniciando secuencia de cierre...")
        # Detiene los componentes en orden inverso
        await application.stop()
        await application.updater.stop()
        await application.shutdown()
        logger.info("Bot cerrado correctamente.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Programa interrumpido.")
