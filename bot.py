import os
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise Exception("❌ No se encontró la variable de entorno TELEGRAM_BOT_TOKEN")
import logging
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ContextTypes

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
json_creds = os.environ.get("GOOGLE_CREDS_JSON")
if not json_creds:
    raise Exception("❌ No se encontró la variable de entorno GOOGLE_CREDS_JSON")

creds_dict = json.loads(json_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Leer credenciales desde variable de entorno
json_creds = os.environ.get("GOOGLE_CREDS_JSON")
if not json_creds:
    raise Exception("❌ No se encontró la variable de entorno GOOGLE_CREDS_JSON")

creds_dict = json.loads(json_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

# --- CONFIGURACIÓN ---
GOOGLE_SHEET_NAME = "Control_SIMs_SMS"  # Cambia al nombre exacto de tu Google Sheet
GOOGLE_TAB_NAME = "Hoja 1"            # Cambia si usas otro nombre de pestaña
# ID del administrador del bot (cámbialo por el tuyo real)
ADMIN_ID = "1006094141"  

# Diccionario en memoria para operadores (se va llenando al usarse)
OPERADORES = { 
"Leo": "1006094141",  # reemplaza con el ID real de Telegram
 "Karla": "987654321"
}

# --- CONEXIÓN A GOOGLE SHEETS ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_TAB_NAME)

# --- FUNCIONES AUXILIARES ---
def obtener_columna(nombre_columna):
    encabezados = sheet.row_values(1)
    if nombre_columna not in encabezados:
        raise ValueError(f"'{nombre_columna}' no está en la hoja")
    return encabezados.index(nombre_columna)

def obtener_fila_por_numero(numero_sim):
    valores = sheet.get_all_records()
    for idx, fila in enumerate(valores, start=2):  # Empieza en fila 2 (fila 1 es encabezado)
        if str(fila.get("Número")) == str(numero_sim):
            return idx, fila
    return None, None

# --- FUNCIONES PRINCIPALES ---
def buscar_sim(app, user_id):
    registros = sheet.get_all_records()
    col_estado = obtener_columna("Estado") + 1
    col_app = obtener_columna("App") + 1
    col_historial = obtener_columna("Historial") + 1
    col_numero = obtener_columna("Número") + 1
    col_iccid = obtener_columna("ICCID") + 1
    col_operador = obtener_columna("Operador") + 1  # Nueva columna en tu hoja

    # Buscar qué operador corresponde a este user_id
    operador_asignado = None
    for nombre, op_id in OPERADORES.items():
        if str(op_id) == str(user_id):
            operador_asignado = nombre
            break

    if not operador_asignado:
        return "🚫 No estás registrado como operador. Pide al admin que te agregue."

    for idx, fila in enumerate(registros, start=2):
        if (
            fila.get("Estado", "").lower() == "activo"
            and (fila.get("App", "") == "" or fila.get("App", "").lower() != app.lower())
            and fila.get("Operador", "").lower() == operador_asignado.lower()
        ):
            # Asignar app y actualizar historial
            sheet.update_cell(idx, col_app, app)
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            historial_actual = fila.get("Historial", "")
            nuevo_historial = f"{historial_actual}\n{fecha}:{app}" if historial_actual else f"{fecha}:{app}"
            sheet.update_cell(idx, col_historial, nuevo_historial)

            numero = fila.get("Número", "No registrado")
            iccid = fila.get("ICCID", "No registrado")

            return (
                f"📱 SIM asignada a {app}:\n"
                f"👤 Operador: {operador_asignado}\n"
                f"🔢 Número: {numero}\n"
                f"🪪 ICCID: {iccid}\n"
            )

    return f"❌ No hay SIMs disponibles para {app} asignadas a tu operador ({operador_asignado})"
def agregar_sim(numero, iccid, compania):
    nueva_fila = [numero, iccid, compania, "Activo", "", "", ""]  # Ajusta columnas según tu hoja
    sheet.append_row(nueva_fila)
    return f"✅ SIM agregada: {numero}"

def eliminar_sim(numero):
    idx, fila = obtener_fila_por_numero(numero)
    if idx:
        sheet.delete_rows(idx)
        return f"🗑️ SIM eliminada: {numero}"
    return f"⚠️ SIM no encontrada: {numero}"

def registrar_uso_sim(numero, app):
    idx, fila = obtener_fila_por_numero(numero)
    if not fila:
        return f"❌ No se encontró la SIM {numero}."
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    col_app = obtener_columna("App") + 1
    col_ultimo_uso = obtener_columna("Último Uso") + 1
    col_historial = obtener_columna("Historial") + 1

    sheet.update_cell(idx, col_app, app)
    sheet.update_cell(idx, col_ultimo_uso, ahora)

    historial_actual = fila.get("Historial", "")
    nuevo_historial = f"{historial_actual}\n[{ahora}] {app}" if historial_actual else f"[{ahora}] {app}"
    sheet.update_cell(idx, col_historial, nuevo_historial)

    return f"✅ SIM {numero} registrada como usada en {app}."

def obtener_historial(numero):
    _, fila = obtener_fila_por_numero(numero)
    if not fila:
        return "❌ No se encontró la SIM."
    historial = fila.get("Historial", "")
    if not historial:
        return f"📱 SIM {numero}\nNo hay historial registrado."
    return f"📱 SIM {numero}\nHistorial de usos:\n{historial}"

def obtener_apps_usadas(numero):
    _, fila = obtener_fila_por_numero(numero)
    if not fila:
        return "❌ No se encontró la SIM."
    historial = fila.get("Historial", "")
    return f"📋 Historial de la SIM {numero}:\n{historial}" if historial else "No hay registros de apps usadas."

def buscar_sims_por_app(nombre_app):
    nombre_app = nombre_app.strip().lower()
    resultados = []
    datos = sheet.get_all_records()
    for fila in datos:
        historial = fila.get("Historial", "")
        numero = fila.get("Número")
        if nombre_app in historial.lower():
            resultados.append(f"📱 {numero}")
    if resultados:
        return f"📄 SIMs que han usado '{nombre_app}':\n" + "\n".join(resultados)
    else:
        return f"🔍 No se encontraron SIMs que hayan usado '{nombre_app}'."

def cmd_agregar_operador(update, context):
    user_id = str(update.effective_user.id)

    # Verificar si es admin
    if user_id != ADMIN_ID:
        update.message.reply_text("🚫 No tienes permisos para agregar operadores.")
        return

    try:
        nombre = context.args[0]
        telegram_id = context.args[1]
    except IndexError:
        update.message.reply_text("Uso correcto: /agregar_operador NOMBRE TELEGRAM_ID")
        return

    # Guardar en Google Sheets
    registros = sheet.get_all_records()
    col_operador = obtener_columna("Operador") + 1
    col_id = obtener_columna("OperadorID") + 1

    # Verificar si ya existe
    for fila in registros:
        if str(fila.get("OperadorID")) == str(telegram_id):
            update.message.reply_text(f"⚠️ El operador {nombre} ya está registrado con ID {telegram_id}.")
            return

    # Insertar en nueva fila
    ultima_fila = len(registros) + 2
    sheet.update_cell(ultima_fila, col_operador, nombre)
    sheet.update_cell(ultima_fila, col_id, telegram_id)

    # Guardar en memoria
    OPERADORES[str(telegram_id)] = nombre

    update.message.reply_text(f"✅ Operador agregado: {nombre} (ID: {telegram_id})")

# --- COMANDOS TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenido al Bot de Control de SIMs.\n"
        "Usa /ayuda para ver comandos disponibles."
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "/buscar [app] - Busca SIM activa no usada para esa app\n"
        "/agregar [numero] [iccid] [compania] - Agrega una nueva SIM\n"
        "/eliminar [numero] - Elimina una SIM\n"
        "/usado [numero] [app] - Registra que una SIM fue usada en una app\n"
        "/historial [numero] - Muestra historial de usos de una SIM\n"
        "/usadas [numero] - Muestra las apps usadas por la SIM\n"
    )
    await update.message.reply_text(texto)

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Uso: /buscar <app>")
        return

    app_name = " ".join(context.args)
    user_id = update.effective_user.id  # Obtenemos el ID del usuario

    resultado = buscar_sim(app_name, user_id)  # <-- pasamos user_id
    await update.message.reply_text(resultado)

async def agregar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Uso: /agregar [numero] [iccid] [compania]")
        return
    numero, iccid, compania = context.args[:3]
    resultado = agregar_sim(numero, iccid, compania)
    await update.message.reply_text(resultado)

async def buscarapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Uso: /buscar <app>")
        return

    app = " ".join(context.args)
    user_id = update.effective_user.id  # ID del usuario que escribió el comando

    resultado = buscar_sim(app, user_id)  # <-- pasamos el user_id
    await update.message.reply_text(resultado)

async def eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /eliminar [numero]")
        return
    numero = context.args[0]
    resultado = eliminar_sim(numero)
    await update.message.reply_text(resultado)

async def usado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /usado [numero] [app]")
        return
    numero = context.args[0]
    app = " ".join(context.args[1:])
    resultado = registrar_uso_sim(numero, app)
    await update.message.reply_text(resultado)

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /historial [numero]")
        return
    numero = context.args[0]
    resultado = obtener_historial(numero)
    await update.message.reply_text(resultado)

async def usadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /usadas [numero]")
        return
    numero = context.args[0]
    resultado = obtener_apps_usadas(numero)
    await update.message.reply_text(resultado)



# --- INICIO DEL BOT ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("buscarapp", buscarapp))
    app.add_handler(CommandHandler("agregar", agregar))
    app.add_handler(CommandHandler("eliminar", eliminar))
    app.add_handler(CommandHandler("usado", usado))
    app.add_handler(CommandHandler("historial", historial))
    app.add_handler(CommandHandler("usadas", usadas))
    app.add_handler(CommandHandler("agregar_operador", cmd_agregar_operador))

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    # ... otros handlers

    print("✅ Bot ejecutándose...")
    app.run_polling()
