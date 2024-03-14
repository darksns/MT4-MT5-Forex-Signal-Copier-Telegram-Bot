#!/usr/bin/env python3
import asyncio
import logging
import os
import random
from metaapi_cloud_sdk import MetaApi
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext

# MetaAPI e Telegram Credentials
API_KEY = os.environ.get("API_KEY")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
TOKEN = os.environ.get("TOKEN")

# Abilita il logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Coda per i segnali di trading
signal_queue = asyncio.Queue()

async def execute_trade(signal: dict):
    """Connette a MetaTrader e esegue il trade basato sul segnale."""
    api = MetaApi(API_KEY)
    try:
        account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
        await account.deploy()
        await account.wait_connected()
        
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        volume = calculate_volume(signal)
        
        if signal['direction'] == 'SELL' or signal['direction'] == 'BUY':
            order_function = connection.create_market_sell_order if signal['direction'] == 'SELL' else connection.create_market_buy_order
            result = await order_function(
                symbol=signal['symbol'],
                volume=volume,
                stopLoss=signal['sl'],
                takeProfit=signal['tp'][0]
            )
            logger.info(f"Trade executed: {result}")
    except Exception as e:
        logger.error(f"Error executing trade: {e}")

def calculate_volume(signal: dict) -> float:
    """Calcola il volume dell'ordine basato su una strategia di rischio."""
    # Esempio: usa un volume fisso o adatta la logica alle tue esigenze
    return 0.01

def parse_signal(message: str) -> dict:
    """Estrae le informazioni dal segnale di trading ricevuto."""
    lines = message.split('\n')
    signal = {
        'symbol': lines[0].strip('📉').strip(),
        'direction': lines[2].split(':')[1].strip().upper(),  # Assicura che la direzione sia in maiuscolo
        'entry': float(lines[3].split(':')[1].strip()),
        'tp': [float(line.split(':')[1].strip()) for line in lines if line.startswith('TP')],
        'sl': float([line for line in lines if line.startswith('❌SL')][0].split(':')[1].strip())
    }
    return signal

async def signal_handler(update: Update, context: CallbackContext) -> None:
    """Gestisce i segnali di trading ricevuti e li mette in coda."""
    signal = parse_signal(update.message.text)
    logger.info(f"Received signal: {signal}")
    await signal_queue.put(signal)

async def process_signals():
    """Processa i segnali di trading dalla coda in modo asincrono."""
    while True:
        signal = await signal_queue.get()
        await execute_trade(signal)
        signal_queue.task_done()

def main():
    """Avvia il bot di Telegram."""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, signal_handler))

    # Avvia il loop di processamento dei segnali in background
    asyncio.create_task(process_signals())

    application.run_polling()

if __name__ == '__main__':
    main()
