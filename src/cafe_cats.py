import pandas as pd
import numpy as np 
from bs4 import BeautifulSoup
import requests
from datetime import datetime 
import time
import pytz
import os
import logging
from utilities import get_cat_page, compare_snapshots

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
        print(f"Getting {filtered['filter']} cats... ")
        filtered_list = get_cat_summary(filtered['url'])

        # compare filtered list with main list
        for cat in results:
            if cat['cat_id'] in [filtered_cat['cat_id'] for filtered_cat in filtered_list]: 
                cat[filtered['filter']] = True
            else: 
                cat[filtered['filter']] = False
    
    return results

def add_cat_page_info(cats): 
    
    print(f'...checking page for {len(cats)} cats...')
    i = 1
    for cat in cats:
        
        # print progress in increments of 20
        if i % 20 == 0: 
            print(f'...checked {i} of {len(cats)} cat pages...')
        
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

def get_latest_snapshot(url, jobtime):

    run_ts = jobtime
    
    print('Getting summary...')
    cats = get_cat_summary(url)
    print('...done')
    
    print('Getting cat filter data...')
    cats = add_cat_filters(cats)
    print('...done')
    
    print('Getting individual cat info (descriptions, type)...')
    cats = add_cat_page_info(cats)
    print('...done')
    
    cat_df = pd.DataFrame(data=cats)
    cat_df['system_import_at'] = run_ts
    
    return cat_df


if __name__ == '__main__':
    
    #################################
    ### RUN SCRIPT + LOG
    #################################


    # configure logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create file handler which logs even debug messages
    fh = logging.FileHandler('/Users/lucasmazzotti/Documents/GitHub/cat-analytics/logs/cafe_cats.log')
    fh.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    # run the script and record how much time it took
    start_time = time.perf_counter()
    
      
    url = 'https://catcafebk.com/our-cats/?'
    jobtime = datetime.fromtimestamp(int(time.time()), tz=pytz.utc)
    
    cat_df = get_latest_snapshot(url, jobtime)
    print('...retrieved latest cat data')
    
    #check if file exists and append
    if os.path.exists('cat_history.csv'):
        print('...adding latest cat data to cat data history')
        cat_history_df = pd.read_csv('cat_history.csv')
        cat_history_df = pd.concat([cat_history_df, cat_df])
        cat_history_df.to_csv('cat_history.csv', index=False)
    
    #otherwise create the file anew
    else:
        cat_df.to_csv('cat_history.csv', index=False)

    end_time = time.perf_counter()
    total_time = end_time - start_time
    logger.info('successful daily_cats.py run!')
    logger.info(f'Script completed in {total_time:0.6f} seconds')

