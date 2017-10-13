#!/usr/bin/python
import smtplib
import datetime

def send_email(subject: str='subject', emailText: str='content of email'):

    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    GMAIL_USERNAME = 'stripsdomzale.notification@gmail.com'
    GMAIL_PASSWORD = 'testdevice07' #CAUTION: This is stored in plain text!

    recipients = []
    recipients.append('jure.macerll@gmail.com')
    recipients.append('peterlive@gmail.com')
    subject = subject

    emailText = emailText
    emailText = "" + emailText + ""



    session = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    session.ehlo()
    session.starttls()
    session.ehlo
    session.login(GMAIL_USERNAME, GMAIL_PASSWORD)

    for recipient in recipients:
        headers = ["From: " + GMAIL_USERNAME,
                   "Subject: " + subject,
                   "To: " + recipient,
                   "MIME-Version: 1.0",
                   "Content-Type: text/html"]
        headers = "\r\n".join(headers)

        session.sendmail(GMAIL_USERNAME, recipient, headers + "\r\n\r\n" + emailText)

    session.quit()