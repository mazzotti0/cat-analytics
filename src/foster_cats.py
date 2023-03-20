import pandas as pd
import numpy as np 
from datetime import datetime 
import time
import pytz
import os
from utilities import get_cat_page, send_new_foster_email, compare_snapshots
from configparser import ConfigParser
import logging



def getFosterInfo():
    
    soup = get_cat_page('https://bbawcfosterteam.wixsite.com/cats/availablecats')
    cats = soup.find('fluid-columns-repeater').find_all('div', class_ = 'comp-kjevao4x5 YzqVVZ wixui-repeater__item')
    jobtime = datetime.fromtimestamp(int(time.time()), tz=pytz.utc)
    
    results_list = []

    for cat in cats:
        
        # get data 
        text_data = cat.find('div', class_='hFQZVn comp-kjevao571 wixui-box')
        cat_image = cat.find('img').attrs['src']
        cat_link = cat.find('a').attrs['href']
        
        # get basic info from text
        cat_name = text_data.find('h4').text
        cat_summary = text_data.find('div', class_="BaOVQ8 tz5f0K comp-kjevl5nv wixui-rich-text").text
        cat_timing = text_data.find('div', class_="BaOVQ8 tz5f0K comp-kjevrpz5 wixui-rich-text").text
        cat_description = text_data.find('div', class_="BaOVQ8 tz5f0K comp-kjevao593 wixui-rich-text").text
        
        # construct an ID for cat (sometimes the name changes to "Name (Reserved)" or "Name (Hold)")
        # this will make it easier to compare snapshots
        cat_id = cat_name.replace(' (reserved)', '').lower()\
                .replace(' (hold)', '')\
                .replace(' ', '-')

        
        results_list.append(
            {'cat_id':cat_id,
            'cat_name':cat_name,
            'cat_summary':cat_summary,
            'cat_timing':cat_timing,
            'cat_description':cat_description,
            'cat_image':cat_image,
            'cat_link':cat_link,
            'full_html':cat}
        )
    df = pd.json_normalize(results_list)
    df['import_at'] = datetime.fromtimestamp(int(time.time()), tz=pytz.utc)
    
    return df

# #TODO: 
#  - add some checks to ensure that we get a new_fosters_df in the expected format 
#  - add some checks to ensure that shape of new_fosters_df is not 0 because that overwrites history

### Run Functions ### 
if __name__ == '__main__': 
    
    # configure logging
    logging.basicConfig(filename='/Users/lucasmazzotti/Documents/GitHub/cat-analytics/logs/foster_cats.log', 
                        filemode='a', 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                        level=logging.INFO)
    logging.info('Logging configured for session')
    
    # time script 
    begin_time = time.perf_counter()
    
    # get last run + current run
    logging.info('getting latest foster information')
    old_fosters_df = pd.read_csv('data/latest_fosters.csv')
    try:
        new_fosters_df = getFosterInfo()
    except Exception as e:
        logging.info(f'error getting new info: {e}')
        logging.info(e)
    new_fosters_df.to_csv('data/latest_fosters.csv', index=False)
    
    # compare new and old runs to determine changes
    logging.info('comparing latest foster data to previous run')
    current_changes_df = compare_snapshots(old_fosters_df, new_fosters_df)
    
    if current_changes_df.shape[0] > 0:
        logging.info('there have been changes since the last pipeline run')
        logging.info('summary of changes: ')
        logging.info(current_changes_df['change_type'].value_counts())
        
        # append changes to change history if it exists
        path = '../output/foster_change_log.csv'
        if os.path.exists(path):
            logging.info('appending to existing change log')
            old_changes_df = pd.read_csv(path)
            changes_df = pd.concat([old_changes_df, current_changes_df])
            changes_df.to_csv(path, index=False)
        else: 
            logging.info('no existing change log found, creating a new one')
            current_changes_df.to_csv(path, index=False)
        
        # if there were rows added, trigger alert
        logging.info('checking for situation: new cat added')
        mask = (current_changes_df['change_type'] == 'row_added')
        if current_changes_df[mask].shape[0] > 0:
            
            logging.info('new cats were added. preparing to send email alerts')
            
            # prepare email creds 
            parser = ConfigParser()
            _ = parser.read('../credentials.cfg')
            sender = parser.get('my_email','my_username')
            password = parser.get('my_email','my_password')
            
            # get recipient list for email
            recipients_df = pd.read_csv('data/recipient_list.csv')
            recipient_list = recipients_df['email'].to_list()
            
            # loop through added cats and send emails
            for cat_id in current_changes_df[mask]['cat_id'].unique():
                cat_email_df = new_fosters_df[new_fosters_df['cat_id'] == cat_id]
                send_new_foster_email(cat_email_df, sender, recipient_list, password)
                logging.info(f"sent email for new cat: {cat_id}")
    else:
        logging.info('no changes since previous pipeline run')
    
    end_time = time.perf_counter()
    total_time = end_time - begin_time
    logging.info(f'script completed in {total_time:0.6f} seconds')

        
    
    
    
    
    
