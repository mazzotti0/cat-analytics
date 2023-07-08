from bs4 import BeautifulSoup
import requests
import datetime
import smtplib
from email.mime.text import MIMEText
from configparser import ConfigParser
import pandas as pd
import numpy as np
import time
import pytz

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

def compare_snapshots(old_df:pd.DataFrame, new_df:pd.DataFrame, join_key:str, exclude_cols:list = None) -> pd.DataFrame:
    '''
    a function to compare two dataframes and return a dataframe specifying what was changed and the type
    inputs: 
        - old_df: the old dataframe
        - new_df: the new dataframe
        - join_key: a string to use for the join key e.g. ['cat_id']
        - exclude_cols: a list of columns to exclude from the comparison e.g. ['foo','bar']
    returns: 
        - a dataframe with the comparison details and timestamps
    '''
    
    # merge dfs and compare
    compare_df = pd.merge(old_df, new_df, how='outer', on=join_key, suffixes=['_old','_new'])
    if exclude_cols:
        loop_cols = [t for t in old_df.columns if join_key not in t and t not in exclude_cols]
    else: 
        loop_cols = [t for t in old_df.columns if join_key not in t]

    # temporarily replace NaN with empty string to properly compare (!= operator with NaN doesn't work)
    compare_df.replace(np.nan,'',regex=True, inplace=True)
    
    # loop through columns and compare values
    for col in loop_cols:
        col_compare_df = compare_df[[c for c in compare_df.columns if col in c]]
        compare_df[f'was_{col}_modified'] = (col_compare_df[f'{col}_old'] != col_compare_df[f'{col}_new'])

    # discard rows where nothing was changed
    compare_df['was_modified'] = compare_df[[col for col in compare_df.columns \
                                            if 'was_' in col]].any(axis=1)
    compare_df = compare_df[compare_df['was_modified'] == True]
    
    # replace empty strings with nulls again
    compare_df.replace(r'^\s*$', np.nan, regex=True, inplace=True)

    # distinguish adds, deletions, modifications
    # need to choose any column other than join key for this as long as it appears in both DFs
    def determine_change(old_val, new_val):
        if pd.isnull(old_val):
            return 'row_added'
        elif pd.isnull(new_val):
            return 'row_deleted'
        else:
            return 'row_modified'
    
    old_val = old_df.columns[2] + '_old'
    new_val = old_df.columns[2] + '_new'
    
    compare_df['change_type'] = compare_df.apply(lambda x: determine_change(x[old_val], x[new_val]), 
                                                axis=1)
    
    compare_df_trim = compare_df[[col for col in compare_df.columns if 'html' not in col]]
    return compare_df_trim

def create_field_history(change_df:pd.DataFrame, id_col:str) -> pd.DataFrame:
    '''
    a function to create a field history based on changes from the most recent pipeline run 
    inputs: 
        - change_df: a dataframe comparing the old and new values from the latest pipeline run
    outputs: 
        - a dataframe with field history including cat_id, field, value, valid_starting_at, valid_ending_at
    '''
    
    rows_modified_starting_df = pd.DataFrame()
    rows_modified_ending_df = pd.DataFrame() 
    valid_starting_ending_at = datetime.datetime.fromtimestamp(int(time.time()), tz=pytz.utc)

    # derive change log 
    for i, row in change_df.iterrows(): 
        
        # derive col names if they were modified
        mod_cols = [col for col in row.index.values if 'was_' in col and row[col] == True and col != 'was_modified']
        old_cols = [col.replace('was_','').replace('_modified','') + '_old' for col in mod_cols]
        new_cols = [col.replace('was_','').replace('_modified','') + '_new' for col in mod_cols]
        
        # get starting ts + add to DF
        this_starting_df = change_df[change_df[id_col] == row[id_col]].melt(id_vars=id_col,
                                    var_name='field',
                                    value_vars=new_cols)
        this_starting_df['valid_starting_at'] = valid_starting_ending_at
        this_starting_df['field'] = this_starting_df['field'].str.replace('_new','')
        rows_modified_starting_df = pd.concat([rows_modified_starting_df, this_starting_df])
        
        # get ending ts + add to DF
        this_ending_df = change_df[change_df[id_col] == row[id_col]].melt(id_vars=id_col,
                                    var_name='field',
                                    value_vars=old_cols)
        this_ending_df['valid_ending_at'] = valid_starting_ending_at
        this_ending_df['field'] = this_ending_df['field'].str.replace('_old','')
        rows_modified_ending_df = pd.concat([rows_modified_ending_df, this_ending_df])

    df = pd.merge(left=rows_modified_starting_df, right=rows_modified_ending_df, how='outer', on=[id_col,'field','value'])
    # if value = np.nan then it means a row was added (NaN --> value) or row deleted (value --> NaN)
    # if row added, this means only valid_starting_at need be included; if row deleted, only valid_ending_at need be included
    # therefore we can drop the unnecessary rows
    df = df[~df['value'].isnull()]

    return df

def update_field_history(last_field_history_df:pd.DataFrame, this_field_history_df:pd.DataFrame, id_col:str) -> pd.DataFrame:
    '''
    basic function to combine new and old field history labels to update valid_starting_at and valid_ending_at timestamps where we have
    multiple records corresponding to a given id,field,value combination
    '''
    df = pd.merge(left=last_field_history_df, right=this_field_history_df, how='outer', on=[id_col,'field','value'])
    df['valid_starting_at'] = np.where(df['valid_starting_at_x'].isnull(), df['valid_starting_at_y'], df['valid_starting_at_x'])
    df['valid_ending_at'] = np.where(df['valid_ending_at_x'].isnull(), df['valid_ending_at_y'], df['valid_ending_at_x'])

    df.drop(columns=['valid_starting_at_x','valid_starting_at_y','valid_ending_at_x','valid_ending_at_y'], inplace=True)
    
    return df
