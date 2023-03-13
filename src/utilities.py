from bs4 import BeautifulSoup
import requests
import datetime
import smtplib
from email.mime.text import MIMEText
from configparser import ConfigParser
import pandas as pd

def get_cat_page(url):

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

def compare_snapshots(old_df, new_df):
    
    # merge dfs and compare
    compare_df = pd.merge(old_df, new_df, how='outer', on='cat_id', suffixes=['_old','_new'])
    loop_cols = [t for t in old_df.columns if 'cat_id' not in t and 'import_at' not in t and 'full_html' not in t]

    for col in loop_cols:
        col_compare_df = compare_df[[c for c in compare_df.columns if col in c]]
        compare_df[f'was_{col}_modified'] = (col_compare_df[f'{col}_old'] != col_compare_df[f'{col}_new'])

    # discard rows where nothing was changed
    compare_df['was_modified'] = compare_df[[col for col in compare_df.columns \
                                            if 'was_' in col]].any(axis=1)
    compare_df = compare_df[compare_df['was_modified'] == True]

    # distinguish adds, deletions, modifications
    def determine_change(old_val, new_val):
        if pd.isnull(old_val):
            return 'row_added'
        elif pd.isnull(new_val):
            return 'row_deleted'
        else:
            return 'row_modified'
    
    compare_df['change_type'] = compare_df.apply(lambda x: determine_change(x['cat_name_old'], x['cat_name_new']), 
                                                axis=1)
    
    compare_df_trim = compare_df[[col for col in compare_df.columns if 'html' not in col]]
    return compare_df_trim
