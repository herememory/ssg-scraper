# ssg-icn-t2.py 파일의 전체 내용

import os
import time
import random
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from supabase import create_client, Client
from webdriver_manager.chrome import ChromeDriverManager

# --- 설정 (T2 지점용) ---
URL = "https://www.ssgdfs.com/kr/customer/initCtStor?tab_no=2&tab_stor_no=07"
ALL_BRANDS_DATA = []
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def save_to_supabase(df: pd.DataFrame, supabase_client: Client):
    if df.empty:
        print("Supabase에 저장할 데이터가 없습니다.")
        return
    print("\nSupabase에 데이터 저장을 시작합니다...")
    df['id'] = df['brand_name'] + '-' + df['location']
    records_to_insert = df.to_dict(orient="records")
    try:
        # 'brand2' 테이블에 저장하도록 수정
        response = supabase_client.table("brand2").upsert(records_to_insert, on_conflict="id").execute()
        print(f"✅ Supabase 'brand2' 테이블 저장 완료! {len(response.data)}개 레코드가 처리되었습니다.")
    except Exception as e:
        print(f"❌ Supabase 저장 중 오류가 발생했습니다: {e}")

# --- 이하 모든 코드는 이전과 동일 ... ---
print("🕵️  'T2 지점 전용 크롤러'를 실행합니다...")
driver = None
try:
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')

    driver_path = ChromeDriverManager().install()
    driver = uc.Chrome(driver_executable_path=driver_path, options=options)
    driver.set_window_size(1920, 1080)
    driver.get(URL)
    print(f"🔗 페이지 접속: {URL}")
    wait = WebDriverWait(driver, 15)

    try:
        popup_close_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.c-modal__close")))
        driver.execute_script("arguments[0].click();", popup_close_button)
        print("✅ 팝업을 성공적으로 닫았습니다.")
        time.sleep(1)
    except Exception:
        print("-> 팝업이 발견되지 않았습니다.")

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.stordFloor li")))
    all_floor_elements = driver.find_elements(By.CSS_SELECTOR, "ul.stordFloor li")
    visible_floor_elements = [elem for elem in all_floor_elements if elem.is_displayed()]
    menu_indices = list(range(len(visible_floor_elements)))

    print(f"📊 화면에 보이는 {len(menu_indices)}개의 메뉴를 '순서대로' 처리합니다.")

    for i in menu_indices:
        floor_name = ""
        try:
            current_button = [elem for elem in driver.find_elements(By.CSS_SELECTOR, "ul.stordFloor li") if elem.is_displayed()][i].find_element(By.TAG_NAME, "a")
            floor_name = current_button.text.strip() or f"인덱스 {i}번 메뉴"
            print(f"🖱️  '{floor_name}' 메뉴 처리 시작...")
            driver.execute_script("arguments[0].click();", current_button)
            time.sleep(random.uniform(2.5, 3.5))

            total_pages = 1
            try:
                page_links = driver.find_elements(By.CSS_SELECTOR, ".listPaging span.page a[data-value]")
                if page_links:
                    all_page_numbers = [int(link.get_attribute("data-value")) for link in page_links]
                    total_pages = max(all_page_numbers) if all_page_numbers else 1
            except Exception as e:
                print(f"    -> 페이지 수 파악 중 오류 발생: {e}. 1페이지만 진행합니다.")
            print(f"    -> '{floor_name}'에는 총 {total_pages}개의 페이지가 있습니다.")

            for page_num in range(1, total_pages + 1):
                print(f"        -> {page_num}페이지 데이터 수집 중...")
                if page_num > 1:
                    try:
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        page_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f".listPaging a.num[data-value='{page_num}'], .listPaging a[data-value='{page_num}'] button.last")))
                        driver.execute_script("arguments[0].click();", page_button)
                        time.sleep(random.uniform(2.5, 4.0))
                    except Exception as page_e:
                        print(f"        -> {page_num}페이지로 이동 실패: {page_e}")
                        break

                brand_items = driver.find_elements(By.CSS_SELECTOR, "ul.floorStore li a.inner")
                if not brand_items and page_num == 1:
                    continue

                for item in brand_items:
                    try: brand_name = item.find_element(By.CLASS_NAME, "brandName").text.strip()
                    except: brand_name = ""
                    if brand_name:
                        try: location = item.find_element(By.CLASS_NAME, "floor").text.strip()
                        except: location = ""
                        try: category = item.find_element(By.CLASS_NAME, "sort").text.strip()
                        except: category = ""
                        try: tel = item.find_element(By.CLASS_NAME, "tel").text.strip()
                        except: tel = ""
                        ALL_BRANDS_DATA.append({"브랜드명": brand_name, "위치": location, "카테고리": category, "연락처": tel})

        except Exception as e:
            print(f"    -> {floor_name} 메뉴 처리 중 오류 발생: {e}")
            continue
except Exception as e:
    print(f"❌ 전체 크롤링 과정에서 심각한 오류가 발생했습니다: {e}")
finally:
    if driver:
        if ALL_BRANDS_DATA:
            df = pd.DataFrame(ALL_BRANDS_DATA)
            df.drop_duplicates(subset=['브랜드명', '위치'], keep='first', inplace=True)
            df.sort_values(by=["위치", "브랜드명"], inplace=True)
            df.reset_index(drop=True, inplace=True)

            print("\n" + "="*50)
            print(df)

            if SUPABASE_URL and SUPABASE_KEY:
                df_to_save = df.rename(columns={'브랜드명': 'brand_name', '위치': 'location', '카테고리': 'category', '연락처': 'tel'})
                supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
                save_to_supabase(df_to_save, supabase)
            else:
                print("\nSupabase Key가 설정되지 않았습니다.")
        else:
            print("\n결과: 수집된 데이터가 없습니다.")
        try:
            print("\n브라우저를 종료합니다.")
            driver.quit()
        except Exception as e:
            print(f"\n브라우저 종료 중 오류 발생: {e}")
