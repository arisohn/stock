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

def crawl_investor_trend(code='005930'):
    """
    네이버 금융 종목 페이지에서 투자자별 매매동향 표를 크롤링하여 DataFrame으로 반환합니다.
    """
    url = f'https://finance.naver.com/item/main.naver?code={code}'
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_selector('body', state='attached')
        html = page.content()
        browser.close()
    soup = BeautifulSoup(html, 'html.parser')

    # 투자자별 매매동향 표 찾기
    section = soup.select_one('div.section.cop_analysis')
    if not section:
        return pd.DataFrame()
    table = section.find('table')
    if not table:
        return pd.DataFrame()

    # 헤더 추출 (2줄 이상일 수 있음)
    thead = table.find('thead')
    headers = []
    if thead:
        header_rows = thead.find_all('tr')
        for tr in header_rows:
            row = [th.get_text(strip=True) for th in tr.find_all('th')]
            headers.append(row)
        # 헤더가 2줄 이상이면 합치기
        if len(headers) > 1:
            merged_headers = []
            for i in range(len(headers[0])):
                h1 = headers[0][i] if i < len(headers[0]) else ''
                h2 = headers[1][i] if len(headers) > 1 and i < len(headers[1]) else ''
                merged_headers.append((h1 + ' ' + h2).strip())
            headers = merged_headers
        else:
            headers = headers[0] if headers else []
    # 데이터 추출
    rows = []
    tbody = table.find('tbody')
    if tbody:
        for tr in tbody.find_all('tr'):
            row = [td.get_text(strip=True) for td in tr.find_all(['th', 'td'])]
            if row:
                rows.append(row)
    # 헤더와 데이터 열 개수 맞추기
    if headers and rows and len(headers) == len(rows[0]):
        df = pd.DataFrame(rows, columns=headers)
    else:
        df = pd.DataFrame(rows)
    return df

if __name__ == '__main__':
    code = sys.argv[1] if len(sys.argv) > 1 else '005930'
    df = crawl_info(code)
    print(df.T)
    print('\n[투자자별 매매동향]')
    investor_df = crawl_investor_trend(code)
    print(investor_df)
