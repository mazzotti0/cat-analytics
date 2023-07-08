import pandas as pd
import numpy as np 
from bs4 import BeautifulSoup
import requests
from datetime import datetime 
import time
import pytz
import os
import logging
from utilities import get_cat_page, compare_snapshots, create_field_history, update_field_history

#################################
### DEFINE FUNCTIONS
#################################

    
def get_cat_summary(url):
    
    soup = get_cat_page(url)
    cat_soup = soup.find('div', class_='flex flex-wrap -m-4')
    cats = cat_soup.find_all('a', href=True)

    results = []
    for cat in cats: 

        #get summary information: link, name, age, gender
        if cat.get('href') != '/': 
            cat_url = 'https://catcafebk.com' + cat.get('href')
            cat_id = cat_url.split('=')[1]
            cat_summary = [i for i in cat.stripped_strings]
            cat_name = cat_summary[0]
            cat_age = cat_summary[1].split('|')[0]
            cat_gender = cat_summary[1].split('|')[1]
            
            results.append(
                {'cat_id':cat_id,
                'url':cat_url,
                'cat_name':cat_name,
                'age':cat_age,
                'gender':cat_gender}
            )
    return results

def add_cat_filters(results):

    filters = [
        {'filter': 'cafe_cat','url': 'https://catcafebk.com/our-cats/?cat-filters%5Bcafe%5D=1'},
        {'filter': 'kid_approved','url': 'https://catcafebk.com/our-cats/?cat-filters%5Bkids%5D=1'},
        {'filter': 'dog_approved','url': 'https://catcafebk.com/our-cats/?cat-filters%5Bdogs%5D=1'},
        {'filter': 'companion_cat','url': 'https://catcafebk.com/our-cats/?cat-filters%5Bcompanion%5D=1'},
        {'filter': 'bonded_pair','url': 'https://catcafebk.com/our-cats/?cat-filters%5Bbonded%5D=1'},
        {'filter': 'single_cat','url': 'https://catcafebk.com/our-cats/?cat-filters%5Bsinglecat%5D=1'}
    ]

    # get list of cats associated with each filter
    for filtered in filters:
        logging.info(f"Getting {filtered['filter']} cats... ")
        filtered_list = get_cat_summary(filtered['url'])

        # compare filtered list with main list
        for cat in results:
            if cat['cat_id'] in [filtered_cat['cat_id'] for filtered_cat in filtered_list]: 
                cat[filtered['filter']] = True
            else: 
                cat[filtered['filter']] = False
    
    return results

def add_cat_page_info(cats): 
    
    logging.info(f'...checking page for {len(cats)} cats...')
    i = 1
    for cat in cats:
        
        # print progress in increments of 20
        if i % 20 == 0: 
            logging.info(f'...checked {i} of {len(cats)} cat pages...')
        
        # parse page info
        page = get_cat_page(cat['url'])
        page_content = page.find('div', class_ = 'px-6 py-12 md:px-12')
        page_strings = [item for item in page_content.stripped_strings]

        cat_type = page_strings[1].split('|')[0]
        cat_description = ' '.join(page_strings[2:-1])
        
        cat['type'] = cat_type
        cat['description'] = cat_description
        i += 1
    
    return cats

def get_latest_snapshot(url, jobtime, debug=False):

    run_ts = jobtime
    
    if debug:
        print('Getting summary...')
    cats = get_cat_summary(url)
    if debug: 
        print('...done')
    
    if debug: 
        print('Getting cat filter data...')
    cats = add_cat_filters(cats)
    if debug:
        print('...done')
    
    if debug:
        print('Getting individual cat info (descriptions, type)...')
    cats = add_cat_page_info(cats)
    if debug:
        print('...done')
    
    #create dataframe and replace empty string values with NaN
    cat_df = pd.DataFrame(data=cats)
    cat_df['system_import_at'] = run_ts
    cat_df.replace(r'^\s*$', np.nan, regex=True, inplace=True)
    
    return cat_df


if __name__ == '__main__':
    
    #################################
    ### RUN SCRIPT + LOG
    #################################


    # configure logging
    logging.basicConfig(filename='/Users/lucasmazzotti/Documents/GitHub/cat-analytics/logs/daily_cats.log', 
                        filemode='a', 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                        level=logging.INFO)
    logging.info('Logging configured for session')

    # run the script and record how much time it took
    start_time = time.perf_counter()
    
      
    url = 'https://catcafebk.com/our-cats/?'
    jobtime = datetime.fromtimestamp(int(time.time()), tz=pytz.utc)
    
    this_cat_df = get_latest_snapshot(url, jobtime)
    logging.info('...retrieved latest cat data')
    
    # check for previous history, if none exists then create it and exit
    if not os.path.exists('data/latest_cafe_cats.csv'):
        msg = 'no previous run found. building baseline and exiting...'
        logging.info(msg)
        this_cat_df.to_csv('data/latest_cafe_cats.csv', index=False)
        exit()
    else: 
        last_cat_df = pd.read_csv('data/latest_cafe_cats.csv')
    
    #overwrite file for latest cat run
    this_cat_df.to_csv('data/latest_cafe_cats.csv', index=False)
    
    # compare new and old runs to determine changes
    logging.info('comparing latest foster data to previous run')
    this_cat_df['cat_id'] = this_cat_df['cat_id'].astype(int)
    last_cat_df['cat_id'] = last_cat_df['cat_id'].astype(int)
    change_df = compare_snapshots(last_cat_df, this_cat_df, join_key='cat_id', exclude_cols=['system_import_at'])
    
    if change_df.shape[0] > 0:
        logging.info('there have been changes since the last pipeline run')
        logging.info('summary of changes: ')
        logging.info(change_df['change_type'].value_counts())

        # append changes to change history if it exists
        path = '../output/cafe_change_log.csv'
        if os.path.exists(path):
            logging.info('appending to existing change log')
            old_changes_df = pd.read_csv(path)
            changes_df = pd.concat([old_changes_df, change_df])
            changes_df.to_csv(path, index=False)
        else: 
            logging.info('no existing change log found, creating a new one')
            change_df.to_csv(path, index=False)
    
        # build field history + merge with existing records
        logging.info('building field history...')
        this_field_history_df = create_field_history(change_df, id_col='cat_id')
        path = '../output/cafe_field_history.csv'
        if not os.path.exists(path):
            this_field_history_df.to_csv(path, index=False)
        else: 
            last_field_history_df = pd.read_csv(path)
            field_history_df = update_field_history(last_field_history_df, this_field_history_df, id_col='cat_id')
            field_history_df.to_csv(path, index=False)
    else: 
        logging.info('no new changes to report')
            
    end_time = time.perf_counter()
    total_time = end_time - start_time
    logging.info('successful daily_cats.py run!')
    logging.info(f'Script completed in {total_time:0.6f} seconds')

