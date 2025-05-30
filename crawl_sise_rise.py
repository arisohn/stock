from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time
import json
import pandas as pd
import random

def get_checkbox():
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

def get_table(checkbox_values):
    """
    선택된 체크박스 항목들에 대한 코스피 테이블 데이터를 가져오는 함수
    Args:
        checkbox_values (list): 선택할 체크박스 value 값들의 리스트 (최대 7개)
    Returns:
        pandas.DataFrame: 선택된 체크박스 항목들의 테이블 데이터
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 네이버 금융 상승률 페이지 접속
        page.goto('https://finance.naver.com/sise/sise_rise.naver')
        
        # 체크박스 항목들이 로드될 때까지 대기
        page.wait_for_selector('input[type="checkbox"]', state="attached")
        
        # 기존 체크박스 해제
        page.evaluate('''() => {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => checkbox.checked = false);
        }''')
        
        # 선택된 체크박스 체크
        for value in checkbox_values:
            page.check(f'input[type="checkbox"][value="{value}"]')
        
        # 체크박스 선택 후 잠시 대기 (동적 렌더링 대응)
        page.wait_for_timeout(1000)
        
        # 적용하기 버튼이 보일 때까지 대기 후 클릭
        page.wait_for_selector('a[href="javascript:fieldSubmit()"]', state="visible")
        page.click('a[href="javascript:fieldSubmit()"]')
        
        # 테이블이 로드될 때까지 대기
        page.wait_for_selector('table.type_2', state="attached")
        
        # HTML 전체를 가져와서 BeautifulSoup으로 파싱
        html = page.content()
        browser.close()
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.select_one('table.type_2')
        
        # 헤더 추출
        headers = []
        first_tr = table.find('tr')
        if first_tr:
            for th in first_tr.find_all(['th', 'td']):
                col = th.get_text(strip=True)
                if col:
                    headers.append(col)
        
        # 데이터 추출
        rows = []
        for tr in table.find_all('tr')[1:]:
            tds = tr.find_all('td')
            if len(tds) > 1:
                row = [td.get_text(strip=True) for td in tds]
                if len(row) >= len(headers):
                    rows.append(row[:len(headers)])
        
        # DataFrame 생성
        df = pd.DataFrame(rows, columns=headers)
        return df

def get_table_all():
    """
    모든 체크박스를 7개씩 그룹으로 나누어 테이블 데이터를 가져오는 함수
    Returns:
        dict: 체크박스 그룹별 테이블 데이터를 담은 딕셔너리
    """
    # 체크박스 항목들 가져오기
    items = get_checkbox()
    
    # fieldIds를 가진 체크박스만 필터링
    field_checkboxes = [item for item in items if item['name'] == 'fieldIds']
    
    # 7개씩 그룹으로 나누기
    checkbox_groups = []
    for i in range(0, len(field_checkboxes), 7):
        group = field_checkboxes[i:i+7]
        checkbox_groups.append(group)
    
    # 각 그룹별로 테이블 데이터 수집
    all_tables = {}
    for group in checkbox_groups:
        group_values = [item['value'] for item in group]
        group_labels = [item['label'] for item in group]
        group_key = ', '.join(group_labels)
        
        # 테이블 데이터 가져오기
        table_data = get_table(group_values)
        all_tables[group_key] = table_data
    
    return all_tables

def grep(stock_name, all_tables):
    """
    특정 종목의 전체 데이터를 출력하는 함수
    Args:
        stock_name (str): 종목명
        all_tables (dict): 체크박스 그룹별 테이블 데이터
    """
    print(f"\n=== {stock_name} 전체 데이터 ===")
    for group_name, table_data in all_tables.items():
        stock_data = table_data[table_data['종목명'] == stock_name]
        if not stock_data.empty:
            print(f"\n[{group_name}]")
            # 기본 정보와 선택된 컬럼만 출력
            basic_cols = ['종목명', '현재가', '전일비', '등락률']
            selected_cols = [col for col in stock_data.columns if col not in ['N'] + basic_cols]
            display_cols = basic_cols + selected_cols
            print(stock_data[display_cols].to_string(index=False))

if __name__ == '__main__':
    # 모든 체크박스 그룹의 테이블 데이터 가져오기
    all_tables = get_table_all()
    
    # HS효성 데이터 출력
    grep('HS효성', all_tables)