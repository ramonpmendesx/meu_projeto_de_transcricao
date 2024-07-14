from flask import Flask, request, render_template, redirect, url_for
from pydub import AudioSegment
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import os
import time
from datetime import datetime
import io

app = Flask(__name__)

# Função para autenticar e criar o serviço do Google Drive
def create_drive_service():
    from google.oauth2 import service_account
    SCOPES = ['https://www.googleapis.com/auth/drive']
    SERVICE_ACCOUNT_FILE = 'path/to/your/service_account.json'
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
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
def download_from_google_drive(drive_service, file_id, output):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(output, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

# Função para converter áudio para MP3
def convert_to_mp3(input_file, output_file):
    audio = AudioSegment.from_file(input_file)
    audio.export(output_file, format="mp3")

# Função para fazer upload de um arquivo para o Google Drive
def upload_to_google_drive(drive_service, file_path, file_name):
    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, mimetype='text/plain')
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded_file.get('id')
    permission = {'type': 'anyone', 'role': 'reader'}
    drive_service.permissions().create(fileId=file_id, body=permission).execute()
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

# Função para enviar e-mail
def send_email(to_address, subject, body, attachment_path, smtp_server, smtp_port, from_address, password):
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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        link = request.form['link']
        email = request.form['email']
        smtp_server = request.form['smtp_server']
        smtp_port = int(request.form['smtp_port'])
        email_user = request.form['email_user']
        email_password = request.form['email_password']
        model_size = request.form['model_size']
        send_email_option = request.form['send_email']

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_id = link.split('/d/')[1].split('/')[0]
        drive_service = create_drive_service()
        original_filename = get_drive_file_name(drive_service, file_id)
        
        if not original_filename:
            return "Erro ao obter o nome do arquivo do Google Drive."

        base_filename = os.path.splitext(original_filename)[0]
        audio_file = f"{base_filename}_{timestamp}.m4a"
        converted_file = f"{base_filename}_{timestamp}.mp3"
        output_file = f"{base_filename}_transcription_{timestamp}.txt"

        start_time = time.time()

        download_from_google_drive(drive_service, file_id, audio_file)
        audio_size = os.path.getsize(audio_file)
        audio_duration = AudioSegment.from_file(audio_file).duration_seconds

        convert_to_mp3(audio_file, converted_file)

        os.system(f"whisper {converted_file} --model {model_size} --language Portuguese --output_format txt --fp16 False")

        txt_file = f"{converted_file.split('.')[0]}.txt"
        with open(txt_file, "r") as file:
            transcription = file.read()

        with open(output_file, "w") as file:
            file.write(transcription)
        
        download_link = upload_to_google_drive(drive_service, output_file, output_file)

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
            send_email(email, subject, body, output_file, smtp_server, smtp_port, email_user, email_password)
            return "E-mail enviado com sucesso."
        else:
            return f"Transcrição concluída. Link para download: {download_link}"

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
