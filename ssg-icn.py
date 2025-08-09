import os
import time
import random
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from supabase import create_client, Client

# --- 설정 ---
URL = "https://www.ssgdfs.com/kr/customer/initCtStor?tab_no=2&tab_stor_no=10"
ALL_BRANDS_DATA = []

# GitHub Secrets에 저장된 Supabase 정보를 환경 변수에서 안전하게 불러옵니다.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def save_to_supabase(df: pd.DataFrame, supabase_client: Client):
    """Pandas DataFrame을 Supabase에 저장하는 함수"""
    if df.empty:
        print("Supabase에 저장할 데이터가 없습니다.")
        return
    print("\nSupabase에 데이터 저장을 시작합니다...")
    df['id'] = df['브랜드명'] + '-' + df['위치']
    records_to_insert = df.to_dict(orient="records")
    try:
        response = supabase_client.table("brands").upsert(records_to_insert, on_conflict="id").execute()
        print(f"✅ Supabase 저장 완료! {len(response.data)}개 레코드가 처리되었습니다.")
    except Exception as e:
        print(f"❌ Supabase 저장 중 오류가 발생했습니다: {e}")


# --- 드라이버 실행 ---
print("🕵️  '드라이버 버전 고정 모드'로 브라우저를 실행합니다...")
driver = None
try:
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # ##############################################################
    # ## 여기를 수정했습니다! (드라이버 버전 130으로 고정) ##
    # ##############################################################
    # GitHub Actions 서버의 크롬 버전에 맞게 드라이버 버전을 130으로 고정합니다.
    driver = uc.Chrome(options=options, version_main=130)
    # ##############################################################

    driver.set_window_size(1920, 1080)
    
    driver.get(URL)
    print(f"🔗 페이지 접속: {URL}")
    wait = WebDriverWait(driver, 15)

    try:
        print("🔍 팝업/쿠키 배너를 감지하고 닫기를 시도합니다...")
        popup_close_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.c-modal__close"))
        )
        driver.execute_script("arguments[0].click();", popup_close_button)
        print("✅ 팝업을 성공적으로 닫았습니다.")
        time.sleep(1)
    except Exception:
        print("-> 팝업이 발견되지 않았습니다. 계속 진행합니다.")

    # --- 이하 크롤링 로직은 동일 ---
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.stordFloor li")))
    all_floor_elements = driver.find_elements(By.CSS_SELECTOR, "ul.stordFloor li")
    visible_floor_elements = [elem for elem in all_floor_elements if elem.is_displayed()]
    menu_indices = list(range(len(visible_floor_elements)))
    
    print(f"📊 화면에 보이는 {len(menu_indices)}개의 메뉴를 '순서대로' 처리합니다.")
    print("-" * 40)
    
    for i in menu_indices:
        floor_name = ""
        try:
            current_button = [
                elem for elem in driver.find_elements(By.CSS_SELECTOR, "ul.stordFloor li") if elem.is_displayed()
            ][i].find_element(By.TAG_NAME, "a")

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
                        page_button = wait.until(EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, f".listPaging a.num[data-value='{page_num}'], .listPaging a[data-value='{page_num}'] button.last")
                        ))
                        driver.execute_script("arguments[0].click();", page_button)
                        time.sleep(random.uniform(2.5, 4.0))
                    except Exception as page_e:
                        print(f"        -> {page_num}페이지로 이동 실패: {page_e}. 이 메뉴의 크롤링을 중단합니다.")
                        break
                
                brand_items = driver.find_elements(By.CSS_SELECTOR, "ul.floorStore li a.inner")
                if not brand_items and page_num == 1:
                    print("            -> 브랜드를 찾지 못했습니다.")
                    continue
                
                print(f"            -> {len(brand_items)}개의 브랜드 발견.")
                for item in brand_items:
                    try: brand_name = item.find_element(By.CLASS_NAME, "brandName").text.strip()
                    except: brand_name = ""
                    try: location = item.find_element(By.CLASS_NAME, "floor").text.strip()
                    except: location = ""
                    try: category = item.find_element(By.CLASS_NAME, "sort").text.strip()
                    except: category = ""
                    try: tel = item.find_element(By.CLASS_NAME, "tel").text.strip()
                    except: tel = ""
                    ALL_BRANDS_DATA.append({"브랜드명": brand_name, "위치": location, "카테고리": category, "연락처": tel})

            print(f"    -> '{floor_name}' 메뉴 처리 완료.")
            print("-" * 40)

        except Exception as e:
            error_msg_context = f"'{floor_name}'" if floor_name else f"인덱스 {i}번"
            print(f"    -> {error_msg_context} 메뉴 처리 중 오류 발생: {e}. 다음 메뉴로 넘어갑니다.")
            print("-" * 40)
            continue
except Exception as e:
    print(f"❌ 전체 크롤링 과정에서 심각한 오류가 발생했습니다: {e}")
finally:
    if driver:
        if ALL_BRANDS_DATA:
            df = pd.DataFrame(ALL_BRANDS_DATA)
            df.drop_duplicates(inplace=True)
            df.sort_values(by=["위치", "브랜드명"], inplace=True)
            df.reset_index(drop=True, inplace=True)
            
            print("\n" + "="*50 + "\n          <<< 최종 크롤링 결과 (중복 제거 및 정렬) >>>")
            print("="*50)
            pd.set_option('display.max_rows', None)
            print(df)
            
            if SUPABASE_URL and SUPABASE_KEY:
                supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
                save_to_supabase(df, supabase)
            else:
                print("\nSupabase URL 또는 Key가 설정되지 않아 데이터베이스 저장을 건너뜁니다.")
        else:
            print("\n결과: 수집된 데이터가 없습니다.")
        try:
            print("\n브라우저를 종료합니다.")
            driver.quit()
        except Exception as e:
            print(f"\n브라우저 종료 중 오류 발생 (이미 닫혔을 수 있음): {e}")
