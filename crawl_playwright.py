from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time
import json

def get_naver_finance_data(stock_code):
    url = f"https://finance.naver.com/item/main.naver?code={stock_code}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(2000)
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        data = {}

        # 시가총액
        def extract_market_cap_from_soup(soup):
            em = soup.find('em', id='_market_sum')
            if em:
                # em 내부 텍스트(개행 포함) 합치기
                em_text = ''.join(em.stripped_strings)
                # '330조', '9,078' 등 분리 추출
                jo = None
                ok = None
                m_jo = re.search(r'([\d,]+)조', em_text)
                if m_jo:
                    jo = int(m_jo.group(1).replace(',', ''))
                # '조' 뒤에 억 단위가 붙어있을 수 있음
                m_ok = re.search(r'조\s*([\d,]+)', em_text)
                if m_ok:
                    ok = int(m_ok.group(1).replace(',', ''))
                if jo is not None and ok is not None:
                    return f"{jo:,}조 {ok:,}억원"
                elif jo is not None:
                    return f"{jo:,}조 0억원"
                # 억 단위만 있을 때
                m3 = re.match(r'([\d,]+)', em_text)
                if m3:
                    ok = int(m3.group(1).replace(',', ''))
                    return f"{ok:,}억원"
                return em_text.strip()
            # 2. em 태그가 없으면, '시가총액' th/td 직접 탐색
            for tr in soup.find_all('tr'):
                th = tr.find('th')
                td = tr.find('td')
                if th and td and '시가총액' in th.text:
                    td_text = td.get_text(separator=' ', strip=True)
                    m = re.search(r'([\d,]+)조\s*([\d,]+)억원', td_text)
                    if m:
                        return f"{int(m.group(1).replace(',', '')):,}조 {int(m.group(2).replace(',', '')):,}억원"
                    m2 = re.search(r'([\d,]+)조', td_text)
                    if m2:
                        return f"{int(m2.group(1).replace(',', '')):,}조 0억원"
                    m3 = re.search(r'([\d,]+)억원', td_text)
                    if m3:
                        return f"{int(m3.group(1).replace(',', '')):,}억원"
            return '정보 없음'
        data['시가총액'] = extract_market_cap_from_soup(soup)

        # 시가총액순위
        rank = None
        for td in soup.find_all('td'):
            td_text = ''.join(td.stripped_strings)
            if '코스피' in td_text and '위' in td_text:
                em_tag = td.find('em')
                if em_tag and em_tag.text.strip().isdigit():
                    rank = f"코스피 {em_tag.text.strip()}위"
                    break
        data['시가총액순위'] = rank if rank else '정보 없음'

        # 상장주식수
        try:
            for th in soup.find_all('th'):
                if '상장주식수' in th.text:
                    td = th.find_next_sibling('td')
                    if td:
                        data['상장주식수'] = td.text.strip()
                        break
            else:
                data['상장주식수'] = '정보 없음'
        except Exception:
            data['상장주식수'] = '정보 없음'

        # 외국인한도주식수(A), 외국인보유주식수(B), 외국인소진율(B/A)
        try:
            found = False
            for table in soup.find_all('table'):
                for tr in table.find_all('tr'):
                    ths = tr.find_all('th')
                    tds = tr.find_all('td')
                    for th, td in zip(ths, tds):
                        if '외국인한도주식수' in th.text:
                            data['외국인한도주식수(A)'] = td.text.strip()
                            found = True
                        if '외국인보유주식수' in th.text:
                            data['외국인보유주식수(B)'] = td.text.strip()
                            found = True
                        if '외국인소진율' in th.text:
                            data['외국인소진율(B/A)'] = td.text.strip()
                            found = True
            if not found:
                for dl in soup.find_all('dl'):
                    dt_texts = [dt.text.strip() for dt in dl.find_all('dt')]
                    if any('외국인한도주식수' in t or '외국인보유주식수' in t or '외국인소진율' in t for t in dt_texts):
                        dts = dl.find_all('dt')
                        dds = dl.find_all('dd')
                        for dt, dd in zip(dts, dds):
                            if '외국인한도주식수' in dt.text:
                                data['외국인한도주식수(A)'] = dd.text.strip()
                            elif '외국인보유주식수' in dt.text:
                                data['외국인보유주식수(B)'] = dd.text.strip()
                            elif '외국인소진율' in dt.text:
                                data['외국인소진율(B/A)'] = dd.text.strip()
                        found = True
                        break
            for key in ['외국인한도주식수(A)', '외국인보유주식수(B)', '외국인소진율(B/A)']:
                if key not in data:
                    data[key] = '정보 없음'
        except Exception:
            data['외국인한도주식수(A)'] = data['외국인보유주식수(B)'] = data['외국인소진율(B/A)'] = '정보 없음'

        # 투자정보 테이블: 투자의견, 목표주가, 52주최고l최저, PER/EPS/PBR/BPS 분리
        try:
            table = soup.find('table', class_='per_table')
            if table:
                for tr in table.find_all('tr'):
                    th = tr.find('th')
                    td = tr.find('td')
                    if not th or not td:
                        continue
                    th_text = th.text.strip()
                    td_text = td.text.strip()
                    # 투자의견 추출 (span.f_up, span.f_down 등 포함)
                    if '투자의견' in th_text:
                        span = td.find('span', class_='f_up') or td.find('span', class_='f_down') or td.find('span')
                        if span:
                            em = span.find('em')
                            if em:
                                score = em.text.strip()
                                opinion = span.text.replace(em.text, '').strip()
                                data['투자의견'] = f"{score} {opinion}" if opinion else score
                        else:
                            data['투자의견'] = td_text
                    # 목표주가 추출 (투자의견 | 목표주가)
                    if '투자의견' in th_text and '목표주가' in th_text:
                        parts = [p.strip() for p in td_text.split('|')]
                        data['투자의견'] = parts[0] if len(parts) > 0 else td_text
                        data['목표주가'] = parts[1] if len(parts) > 1 else ''
                    # PER/EPS(2025.03) 추출
                    if th_text.startswith('PER') and re.search(r'\d{4}\.\d{2}', th_text):
                        per_em = td.find('em', id='_per')
                        eps_em = td.find('em', id='_eps')
                        if per_em:
                            data['PER(2025.03)'] = per_em.text.strip()
                        else:
                            per_match = re.search(r'([\d.,]+)배', td_text)
                            if per_match:
                                data['PER(2025.03)'] = per_match.group(1)
                        if eps_em:
                            data['EPS(2025.03)'] = eps_em.text.strip()
                        else:
                            eps_match = re.search(r'([\d,]+)원', td_text)
                            if eps_match:
                                data['EPS(2025.03)'] = eps_match.group(1)
                    # 기존 로직 유지
                    elif '52주최고' in th_text and '최저' in th_text:
                        data['52주최고l최저'] = td_text
                    elif th_text.startswith('추정PER'):
                        per_match = re.search(r'([\d.,]+)배', td_text)
                        eps_match = re.search(r'([\d,]+)원', td_text)
                        if per_match:
                            data['PER(추정)'] = per_match.group(1)
                        if eps_match:
                            data['EPS(추정)'] = eps_match.group(1)
                    elif th_text.startswith('PBR') and re.search(r'\d{4}\.\d{2}', th_text):
                        pbr_match = re.search(r'([\d.,]+)배', td_text)
                        bps_match = re.search(r'([\d,]+)원', td_text)
                        if pbr_match:
                            data['PBR(2025.03)'] = pbr_match.group(1)
                        if bps_match:
                            data['BPS(2025.03)'] = bps_match.group(1)
            if '투자의견' not in data:
                data['투자의견'] = '정보 없음'
            for key in ['목표주가', '52주최고l최저', 'PER(2025.03)', 'EPS(2025.03)', 'PER(추정)', 'EPS(추정)', 'PBR(2025.03)', 'BPS(2025.03)']:
                if key not in data:
                    data[key] = '정보 없음'
        except Exception:
            data['투자의견'] = '정보 없음'
            for key in ['목표주가', '52주최고l최저', 'PER(2025.03)', 'EPS(2025.03)', 'PER(추정)', 'EPS(추정)', 'PBR(2025.03)', 'BPS(2025.03)']:
                data[key] = '정보 없음'
        browser.close()
        return data

def get_checkbox_items():
    """
    네이버 금융 상승률 페이지에서 체크박스 항목들을 가져오는 함수
    Returns:
        list: 체크박스 항목들의 리스트
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 네이버 금융 상승률 페이지 접속
        page.goto('https://finance.naver.com/sise/sise_rise.naver')
        
        # 체크박스 항목들이 로드될 때까지 대기
        page.wait_for_selector('input[type="checkbox"]', state="attached")
        
        # 체크박스 항목들 가져오기
        checkbox_items = page.evaluate('''() => {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            return Array.from(checkboxes).map(checkbox => ({
                id: checkbox.id,
                name: checkbox.name,
                value: checkbox.value,
                label: checkbox.nextElementSibling?.textContent?.trim() || ''
            }));
        }''')
        
        browser.close()
        return checkbox_items

if __name__ == '__main__':
    stock_code = '005930'
    result = get_naver_finance_data(stock_code)
    for k, v in result.items():
        print(f'{k}: {v}')

    # 체크박스 항목들 가져오기
    items = get_checkbox_items()
    
    # 결과 출력
    print(json.dumps(items, ensure_ascii=False, indent=2))
