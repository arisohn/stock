from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import re
import sys

def crawl_info(code='005930'):
    url = f'https://finance.naver.com/item/main.naver?code={code}'
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_selector('body', state='attached')
        html = page.content()
        browser.close()
    soup = BeautifulSoup(html, 'html.parser')

    data = {}
    # 시가총액, 시가총액순위, 상장주식수
    first_table = soup.select_one('div#tab_con1 div.first table')
    if first_table:
        for tr in first_table.select('tr'):
            th = tr.find('th')
            td = tr.find('td')
            if not th or not td:
                continue
            label = th.get_text(strip=True)
            if '시가총액' in label:
                # td 전체의 텍스트에서 '억원' 앞까지 추출
                td_text = td.get_text(separator=' ', strip=True)
                m = re.search(r'([\d,]+조)?\s*([\d,]+)?\s*억원', td_text)
                if m:
                    value = (m.group(1) or '').strip() + (' ' if m.group(1) and m.group(2) else '') + (m.group(2) or '')
                    data['시가총액'] = value + '억원'
            if '시가총액순위' in label:
                em = td.find('em')
                if em:
                    data['시가총액순위'] = em.get_text(strip=True)
            if '상장주식수' in label:
                em = td.find('em')
                if em:
                    data['상장주식수'] = em.get_text(strip=True)
    # 외국인한도주식수, 외국인보유주식수, 외국인소진율
    gray_tables = soup.select('div#tab_con1 div.gray table')
    if gray_tables:
        # 첫 번째 gray 테이블이 외국인 관련
        rows = gray_tables[0].find_all('tr')
        if len(rows) > 0:
            em = rows[0].find('em')
            if em:
                data['외국인한도주식수'] = em.get_text(strip=True)
        if len(rows) > 1:
            em = rows[1].find('em')
            if em:
                data['외국인보유주식수'] = em.get_text(strip=True)
        if len(rows) > 2:
            em = rows[2].find('em')
            if em:
                data['외국인소진율'] = em.get_text(strip=True)
    # 투자의견, 목표주가, 52주최고, 52주최저
    rwidth_table = soup.select_one('div#tab_con1 table.rwidth')
    if rwidth_table:
        trs = rwidth_table.select('tr')
        if len(trs) > 0:
            # 투자의견, 목표주가
            tds = trs[0].find_all('td')
            if tds:
                # 투자의견
                opinion_span = tds[0].find('span', class_='f_up')
                if opinion_span:
                    ems = opinion_span.find_all('em')
                    if len(ems) > 0:
                        data['투자의견'] = ems[0].get_text(strip=True)
                        # 투자의견 텍스트(매수 등)는 em 다음 텍스트
                        if ems[0].next_sibling:
                            data['투자의견'] += ' ' + ems[0].next_sibling.strip()
                    # 목표주가
                    if len(ems) > 1:
                        data['목표주가'] = ems[1].get_text(strip=True)
                # 목표주가(바로 뒤 em)
                if not data.get('목표주가'):
                    ems = tds[0].find_all('em')
                    if len(ems) > 1:
                        data['목표주가'] = ems[1].get_text(strip=True)
        if len(trs) > 1:
            # 52주최고, 52주최저
            tds = trs[1].find_all('td')
            if tds:
                ems = tds[0].find_all('em')
                if len(ems) > 1:
                    data['52주최고'] = ems[0].get_text(strip=True)
                    data['52주최저'] = ems[1].get_text(strip=True)

    # PER, EPS, 추정PER, 추정EPS, PBR, BPS, 배당수익률
    per_table = soup.select_one('div#tab_con1 table.per_table')
    if per_table:
        tbodies = per_table.find_all('tbody')
        trs = per_table.find_all('tr')
        # PER, EPS
        if len(trs) > 0:
            tds = trs[0].find_all('td')
            if tds:
                ems = tds[0].find_all('em')
                if len(ems) > 1:
                    data['PER'] = ems[0].get_text(strip=True)
                    data['EPS'] = ems[1].get_text(strip=True)
        # 추정PER, 추정EPS
        if len(trs) > 1:
            tds = trs[1].find_all('td')
            if tds:
                ems = tds[0].find_all('em')
                if len(ems) > 1:
                    data['추정PER'] = ems[0].get_text(strip=True)
                    data['추정EPS'] = ems[1].get_text(strip=True)
        # PBR, BPS
        if len(trs) > 2:
            tds = trs[2].find_all('td')
            if tds:
                ems = tds[0].find_all('em')
                if len(ems) > 1:
                    data['PBR'] = ems[0].get_text(strip=True)
                    data['BPS'] = ems[1].get_text(strip=True)
        # 배당수익률
        if len(trs) > 3:
            tds = trs[3].find_all('td')
            if tds:
                em = tds[0].find('em')
                if em:
                    data['배당수익률'] = em.get_text(strip=True) + '%'

    # 동일업종PER, 동일업종등락률
    gray_tables = soup.select('div#tab_con1 div.gray table')
    if len(gray_tables) > 1:
        # 마지막 gray 테이블이 동일업종 PER
        last_table = gray_tables[-1]
        trs = last_table.find_all('tr')
        if len(trs) > 0:
            em = trs[0].find('em')
            if em:
                data['동일업종PER'] = em.get_text(strip=True)
        if len(trs) > 1:
            em = trs[1].find('em')
            if em:
                data['동일업종등락률'] = em.get_text(strip=True)
    # 모든 필드가 빠짐없이 나오도록 None 처리
    fields = [
        '시가총액', '시가총액순위', '상장주식수', '외국인한도주식수', '외국인보유주식수', '외국인소진율',
        '투자의견', '목표주가', '52주최고', '52주최저', 'PER', 'EPS', '추정PER', '추정EPS',
        'PBR', 'BPS', '배당수익률', '동일업종PER', '동일업종등락률'
    ]
    for f in fields:
        if f not in data:
            data[f] = None
    df = pd.DataFrame([data])
    return df

if __name__ == '__main__':
    code = sys.argv[1] if len(sys.argv) > 1 else '005930'
    df = crawl_info(code)
    print(df.T)
