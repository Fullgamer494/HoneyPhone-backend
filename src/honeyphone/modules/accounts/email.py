from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from honeyphone.core.config import settings


class EmailDeliveryError(RuntimeError):
    pass


def _send(recipient: str, subject: str, headline: str, description: str, link: str, button: str) -> None:
    client = boto3.client("sesv2", region_name=settings.aws_region)
    html = (
        '<div style="background:#08090a;color:#f4f4f4;padding:36px;font-family:Arial,sans-serif">'
        '<div style="max-width:520px;margin:auto;border:1px solid #303234;border-radius:20px;padding:30px">'
        '<p style="letter-spacing:.18em;color:#aaa;font-size:12px">HONEYPHONE</p>'
        f'<h1 style="font-size:25px">{headline}</h1><p style="color:#c4c6c7;line-height:1.6">{description}</p>'
        f'<p style="margin:28px 0"><a href="{link}" style="background:#f4f4f4;color:#101112;border-radius:10px;padding:13px 18px;text-decoration:none;font-weight:bold">{button}</a></p>'
        '<p style="color:#888;font-size:12px;line-height:1.5">Si no solicitaste esto, puedes ignorar este correo. El enlace caduca y solo funciona una vez.</p>'
        '</div></div>'
    )
    text = f"{headline}\n\n{description}\n\n{button}: {link}\n\nSi no solicitaste esto, ignora este mensaje."
    try:
        client.send_email(
            FromEmailAddress=f"HoneyPhone <{settings.email_from}>",
            Destination={"ToAddresses": [recipient]},
            Content={"Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": text, "Charset": "UTF-8"}, "Html": {"Data": html, "Charset": "UTF-8"}},
            }},
        )
    except (BotoCoreError, ClientError) as exc:
        raise EmailDeliveryError("No se pudo enviar el correo por Amazon SES.") from exc


def send_verification(recipient: str, raw_token: str) -> None:
    link = f"{settings.public_base_url.rstrip('/')}/account/verify#token={quote(raw_token)}"
    _send(recipient, "Confirma tu correo de HoneyPhone", "Confirma tu correo", "Confirma que esta dirección te pertenece para activar tu cuenta HoneyPhone.", link, "Confirmar correo")


def send_password_reset(recipient: str, raw_token: str) -> None:
    link = f"{settings.public_base_url.rstrip('/')}/account/reset#token={quote(raw_token)}"
    _send(recipient, "Recupera tu acceso a HoneyPhone", "Crea una contraseña nueva", "Recibimos una solicitud para restablecer la contraseña de tu cuenta.", link, "Restablecer contraseña")
