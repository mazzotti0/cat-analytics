from bs4 import BeautifulSoup
import requests
import datetime
import smtplib
from email.mime.text import MIMEText
from configparser import ConfigParser

def getCatPage(url):

    parser = ConfigParser()
    _ = parser.read('../credentials.cfg')
    browser = parser.get('my_browser','user_agent')

    headers = {'User-Agent':browser}
    
    page = requests.get(url, headers=headers)
    
    if page.status_code == 200: 
        soup = BeautifulSoup(page.content, 'html.parser')
        # print("got site data")
        return soup
    else: 
        print("Error: ", page.status_code)
        print(page.content)
        return
    
def send_new_foster_email(df, sender, recipient_list, password): 
    '''
    send an email alert about a new cat
    
    inputs: 
        - df: 1-row dataframe with the needed info (summary, html)
        - sender: (str) from address of email 
        - recipient_list: list of emails to send to
        - password: (str) gmail app password
    '''
    
    sender_email = sender
    sender_password = password
    
    #pull text data out of cat df 
    header = df['cat_summary'].values[0]
    body = df['full_html'].values[0]
    
    subject = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}: New foster cat alert! {header}"
    body = f'''
        <html>
            <body>
            <h1> New cat alert! </h1>
                {body}
            </body>
        </html>
        '''
    html_message = MIMEText(body, 'html')
    html_message['Subject'] = subject
    html_message['From'] = sender_email
    html_message['To'] = ", ".join(recipient_list)

    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, recipient_list, html_message.as_string())
    server.quit()
