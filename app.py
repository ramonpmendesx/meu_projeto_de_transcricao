# Instalar dependências
!pip install git+https://github.com/openai/whisper.git
!sudo apt update && sudo apt install ffmpeg
!pip install requests pydub google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client ipywidgets tqdm

from pydub import AudioSegment
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.colab import auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import os
import time
from datetime import datetime
import ipywidgets as widgets
from IPython.display import display, clear_output
from tqdm.notebook import tqdm
import io

# Função para autenticar e criar o serviço do Google Drive
def create_drive_service():
    auth.authenticate_user()
    drive_service = build('drive', 'v3')
    return drive_service

# Função para obter o nome do arquivo do Google Drive
def get_drive_file_name(drive_service, file_id):
    try:
        file = drive_service.files().get(fileId=file_id).execute()
        return file['name']
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

# Função para baixar o arquivo do Google Drive
def download_from_google_drive(drive_service, file_id, output, log_output):
    log_output.append_stdout("Etapa 1 de 5: Baixando arquivo do Google Drive...\n")
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(output, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

# Função para converter áudio para MP3
def convert_to_mp3(input_file, output_file, log_output):
    log_output.append_stdout("Etapa 2 de 5: Convertendo arquivo para MP3...\n")
    audio = AudioSegment.from_file(input_file)
    audio.export(output_file, format="mp3")

# Função para fazer upload de um arquivo para o Google Drive
def upload_to_google_drive(drive_service, file_path, file_name, log_output):
    log_output.append_stdout("Etapa 4 de 5: Fazendo upload do arquivo para o Google Drive...\n")
    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, mimetype='text/plain')

    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    
    file_id = uploaded_file.get('id')
    permission = {
        'type': 'anyone',
        'role': 'reader',
    }
    drive_service.permissions().create(fileId=file_id, body=permission).execute()

    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

# Função para enviar e-mail
def send_email(to_address, subject, body, attachment_path, smtp_server, smtp_port, from_address, password, log_output):
    log_output.append_stdout("Etapa 5 de 5: Enviando e-mail...\n")
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    attachment = open(attachment_path, "rb")
    part = MIMEBase('application', 'octet-stream')
    part.set_payload((attachment).read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(attachment_path)}")
    msg.attach(part)

    server = smtplib.SMTP_SSL(smtp_server, smtp_port)
    server.login(from_address, password)
    text = msg.as_string()
    server.sendmail(from_address, to_address, text)
    server.quit()

# Função para converter segundos para minutos e segundos
def format_time(seconds):
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{int(minutes)} minutos e {int(seconds)} segundos"

# Função principal de processamento
def process_file(link, email, smtp_server, smtp_port, email_user, email_password, model_size, send_email_option, log_output):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Extrair nome do arquivo do link do Google Drive
    file_id = link.split('/d/')[1].split('/')[0]
    drive_service = create_drive_service()
    original_filename = get_drive_file_name(drive_service, file_id)
    
    if not original_filename:
        log_output.append_stdout("Erro ao obter o nome do arquivo do Google Drive.\n")
        return
    
    # Dividir o nome do arquivo e adicionar timestamp
    base_filename = os.path.splitext(original_filename)[0]
    audio_file = f"{base_filename}_{timestamp}.m4a"
    converted_file = f"{base_filename}_{timestamp}.mp3"
    output_file = f"{base_filename}_transcription_{timestamp}.txt"

    start_time = time.time()

    download_from_google_drive(drive_service, file_id, audio_file, log_output)
    audio_size = os.path.getsize(audio_file)
    audio_duration = AudioSegment.from_file(audio_file).duration_seconds

    convert_to_mp3(audio_file, converted_file, log_output)

    log_output.append_stdout("Etapa 3 de 5: Transcrevendo áudio...\n")
    os.system(f"whisper {converted_file} --model {model_size} --language Portuguese --output_format txt --fp16 False")

    txt_file = f"{converted_file.split('.')[0]}.txt"
    with open(txt_file, "r") as file:
        transcription = file.read()
        log_output.append_stdout("Transcrição original:\n")
        log_output.append_stdout(transcription + "\n")

    with open(output_file, "w") as file:
        file.write(transcription)
    
    download_link = upload_to_google_drive(drive_service, output_file, output_file, log_output)
    log_output.append_stdout(f"Link para download do arquivo: {download_link}\n")

    end_time = time.time()
    total_time = end_time - start_time
    total_time_formatted = format_time(total_time)

    if send_email_option == 'Sim':
        subject = "Transcrição Concluída"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);">
                <h2 style="color: #2c3e50;">Parabéns! Aqui está a sua transcrição concluída</h2>
                <p style="font-size: 16px; color: #2c3e50;">A transcrição do seu áudio foi concluída com sucesso. Aqui estão os detalhes:</p>
                <ul style="font-size: 16px; color: #2c3e50;">
                    <li><b>Duração do Áudio:</b> {audio_duration:.2f} segundos</li>
                    <li><b>Tamanho do Arquivo Original:</b> {audio_size / (1024*1024):.2f} MB</li>
                    <li><b>Tempo Total de Execução:</b> {total_time_formatted}</li>
                </ul>
                <p style="font-size: 16px; color: #2c3e50;">Clique no link abaixo para baixar o arquivo transcrito:</p>
                <a href="{download_link}" style="display: inline-block; font-size: 16px; color: #ffffff; background-color: #007bff; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Baixar Transcrição</a>
            </div>
        </body>
        </html>
        """
        send_email(email, subject, body, output_file, smtp_server, smtp_port, email_user, email_password, log_output)
        log_output.append_stdout("E-mail enviado com sucesso.\n")
    else:
        log_output.append_stdout(f"Transcrição concluída. Link para download: {download_link}\n")

# Função para atualizar a visibilidade dos campos de e-mail
def update_email_fields(change):
    if change['new'] == 'Sim':
        email_fields.layout.display = 'block'
    else:
        email_fields.layout.display = 'none'

# Criar widgets para a interface do usuário
link_input = widgets.Text(
    value='',
    placeholder='Link de compartilhamento do Google Drive',
    description='Link:',
    disabled=False
)

model_size_input = widgets.Dropdown(
    options=['tiny', 'base', 'small', 'medium', 'large'],
    value='medium',
    description='Qualidade:',
    disabled=False
)

send_email_input = widgets.Dropdown(
    options=['Sim', 'Não'],
    value='Sim',
    description='Enviar por e-mail:',
    disabled=False
)

email_input = widgets.Text(
    value='ramon@szsolucoes.com.br',
    placeholder='E-mail de destino',
    description='E-mail:',
    disabled=False
)

smtp_server_input = widgets.Text(
    value='mail.szsolucoes.com.br',
    placeholder='Servidor SMTP',
    description='SMTP:',
    disabled=False
)

smtp_port_input = widgets.Text(
    value='465',
    placeholder='Porta SMTP',
    description='Porta:',
    disabled=False
)

email_user_input = widgets.Text(
    value='ramon.mendes@szsolucoes.com.br',
    placeholder='E-mail do remetente',
    description='Usuário:',
    disabled=False
)

email_password_input = widgets.Password(
    value='SZ@R@M0n',
    placeholder='Senha do e-mail',
    description='Senha:',
    disabled=False
)

email_fields = widgets.VBox([
    email_input,
    smtp_server_input,
    smtp_port_input,
    email_user_input,
    email_password_input
])

log_output = widgets.Output()

button = widgets.Button(description="Processar")

def on_button_clicked(b):
    with log_output:
        clear_output()
        process_file(
            link_input.value,
            email_input.value,
            smtp_server_input.value,
            smtp_port_input.value,
            email_user_input.value,
            email_password_input.value,
            model_size_input.value,
            send_email_input.value,
            log_output
        )

button.on_click(on_button_clicked)
send_email_input.observe(update_email_fields, names='value')

# Exibir widgets
display(
    link_input,
    model_size_input,
    send_email_input,
    email_fields,
    button,
    log_output
)

# Inicialmente ocultar os campos de e-mail se a opção inicial for "Não"
update_email_fields({'new': send_email_input.value})
