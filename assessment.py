import os
import re
import datetime
import string
import csv
import time
from urllib.parse import quote
from urllib.request import urlretrieve
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException




# Store chrome data to avoid conflict with current personal installations of chrome
current_directory = os.getcwd()
chrome_user_data_storage = os.path.join(current_directory, "chrome_user_data")
chrome_options = Options()
chrome_options.add_argument(f"--user-data-dir={chrome_user_data_storage}")

money_regex = r'\$[\d,]+(\.\d+)?|\d+\s*(?:million|billion|trillion)?\s*(?:dollars|USD|usd)?'



class Article:
    def __init__(self, title=None, date=None, description=None, picture_url=None):
        self.title = title
        self.date = date
        self.description = description
        self.picture_url = picture_url
        self.phrasecount = self.count_phrases(self.description, self.title)
        self.hasmoney = self.check_money()
        self.picture_filename = self.get_filename()
        self.picture= self.download_picture()

        #a regex check that can be reused by both criterias for money indicatiors
    def check_money_format(self, text):
        match = re.search(money_regex, text, re.IGNORECASE)
        if match:
            return True
        else:
            return False

    def check_money(self):
        if self.title and self.check_money_format(self.title):
            return True
        elif self.description and self.check_money_format(self.description):
            return True
        else:
            return False

    def sanitize_filename(self, filename):
        # Remove invalid characters from the filename
        valid_chars = "-_() %s%s." % (string.ascii_letters, string.digits)
        return ''.join(c for c in filename if c in valid_chars)

    #after sanitizing input gets the filename for the image to be passed onto the downloaded fil as well
    def get_filename(self):
        if self.picture_url:
            filename = os.path.basename(self.picture_url)
            filename = self.sanitize_filename(filename)
            return filename
        else:
            return None


    def count_phrases(self, *attributes):
        phrase_count = 0
        for attribute in attributes:
            if attribute is not None:
                sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', attribute)
                phrase_count += len(sentences)
        return phrase_count
    #will download the picture and store in a folder that will be created if doesn't exist
    def download_picture(self):
        if self.picture_url:
            folder_path = "article_pics"
            os.makedirs(folder_path, exist_ok=True)  # Create the folder if it doesn't exist
            picture_path = os.path.join(folder_path, self.picture_filename)
            try:
                urlretrieve(self.picture_url, picture_path)
                print(f"Picture downloaded: {picture_path}")
            except Exception as e:
                print(f"Failed to download picture from: {self.picture_url}, Error: {e}")
        else:
            print("No picture URL available")


class QueryElements:
    def __init__(self, query=None, months_to_trace=None, sections=None):
        self.query = quote(query)
        self.default_url = "https://www.nytimes.com/search?"
        self.sections = sections
        self.months = int(months_to_trace)
        self.driver = webdriver.Chrome(options=chrome_options)
        #the categories attribute is hardcoded as I found tricky to scrape the categories from their dropdown menu
        self.categories = {
            'arts': 'Arts%7Cnyt%3A%2F%2Fsection%2F6e6ee292-b4bd-5006-a619-9ceab03524f2',
            'books': 'Books%7Cnyt%3A%2F%2Fsection%2F550f75e2-fc37-5d5c-9dd1-c665ac221b49',
            'business': 'Business%7Cnyt%3A%2F%2Fsection%2F0415b2b0-513a-5e78-80da-21ab770cb753',
            'magazine': 'Magazine%7Cnyt%3A%2F%2Fsection%2Fa913d1fb-3cdf-556b-9a81-f0b996a1a202',
            'movies': 'Movies%7Cnyt%3A%2F%2Fsection%2F62b3d471-4ae5-5ac2-836f-cb7ad531c4cb',
            'new york': 'New%20York%7Cnyt%3A%2F%2Fsection%2F39480374-66d3-5603-9ce1-58cfa12988e2',
            'opinion': 'Opinion%7Cnyt%3A%2F%2Fsection%2Fd7a71185-aa60-5635-bce0-5fab76c7c297',
            'technology': 'Technology%7Cnyt%3A%2F%2Fsection%2F4224240f-b1ab-50bd-881f-782d6a3bc527',
        }
        self.search_url = self.run_query()


      #reading from the variables.ini file checks for how many months wanna trace back the search and append it to the query.
      #However, it truncates any day over 28 to 28 in february and over 31 to 30 on the rest months for ease of use
    def get_start_date(self):
        current_date = datetime.datetime.now()
        modified_month = current_date.month - self.months
        modified_year = current_date.year

        if modified_month <= 0:
            modified_year -= 1
            modified_month += 12

        modified_date = current_date.replace(year=modified_year, month=modified_month, day=1)

        if modified_date.month == 2:
            modified_date = modified_date.replace(day=min(current_date.day, 28))
        elif modified_date.day > 30:
            modified_date = modified_date.replace(day=30)

        while modified_date.month == current_date.month:
            modified_date -= datetime.timedelta(days=1)

        return modified_date.strftime("%Y%m%d")

    #after reading each element of the variables file it will append the results in order to create a query that is compliant to the GET format of the NYT
    def run_query(self):
        query_url = self.default_url

        if self.query:
            query_url += f"&query={self.query}"

        if self.sections is not None and len(self.sections) != 0:
            query_url += f"&sections="
            for section in self.sections:
                if section in self.categories:
                    query_url += self.categories[section]

        if self.months is not None and self.months > 0:
            start_date = self.get_start_date()
            query_url += f"&startDate={start_date}"

        print(query_url)
        return query_url

    #using the appended query from above attempts to retrieve the desired information and retrieves a list of objects to be added to the excel file
    def get_articles(self):
        articles = []
        self.driver.get(self.search_url)
        while True:
            try:
                show_more_button = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'button[data-testid="search-show-more-button"]')
                    )
                )
                show_more_button.click()
                WebDriverWait(self.driver, 15).until(EC.staleness_of(show_more_button))
            except Exception:
                break

        elements = self.driver.find_elements(By.CLASS_NAME, "css-1kl114x")
        for element in elements:
            try:
                date_element = element.find_element(By.CSS_SELECTOR, '.css-17ubb9w')
                date = date_element.get_attribute("aria-label")
            except NoSuchElementException:
                date = None

            try:
                title = element.find_element(By.XPATH, './/a/h4').text
            except NoSuchElementException:
                title = None

            try:
                description = element.find_element(By.XPATH, ".//p[@class='css-16nhkrn']").text

            except NoSuchElementException:
                description = None

            try:
                img_element = element.find_element(By.CSS_SELECTOR, "img[class='css-rq4mmj']")
                picture_url = img_element.get_attribute("src")
                if picture_url:
                    jpg_index = picture_url.find(".jpg")
                    if jpg_index != -1:
                        picture_url = picture_url[:jpg_index + 4]
            except NoSuchElementException:
                picture_url = None
            #create an object that holds the article so it can compute number of phrases, if it shows money and filenames
            article = Article(title, date, description, picture_url)
            articles.append(article)

        return articles



    #closes the web driver and frees up resources
    def cleanup(self):
        self.driver.quit()

#this will create and read the variables file in case it doesn't exists
def read_variables_file(file_path):
    variables = {}
    try:
        with open(file_path, 'r') as file:
            # Read the file line by line
            for line in file:
                # create comments in the ini file
                if line.startswith('#'):
                    continue

                # Split each line into key-value pair
                key, value = line.strip().split('=')

                # Store the key-value pair in the dictionary
                variables[key] = value
        print(f"Variables read from '{file_path}':")
        print(variables)
        return variables
    except FileNotFoundError:
        # File doesn't exist, create it and add sample variables
        with open(file_path, 'w') as file:
            file.write("query=mr beast\n")
            file.write("#please add the desired distinct sections separated by commas\n")
            file.write("sections=any\n")
            file.write("months_to_search=0\n")

        print(f"File '{file_path}' created with sample variables.")
        return read_variables_file(file_path)

#Opens a CSV file to store the results. if doesn't exist: creates a CSV
def save_articles_to_csv(articles, filename):
    fieldnames = ['Title', 'Date', 'Description', 'Picture URL', 'Filename', 'Has Money', 'Number of Phrases']
    folder_path = "article_pics"
    os.makedirs(folder_path, exist_ok=True)  # Create the folder if it doesn't exist

    file_exists = os.path.exists(filename)
    with open(filename, 'a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for article in articles:
            row = {
                'Title': article.title,
                'Date': article.date,
                'Description': article.description,
                'Picture URL': article.picture_url,  # Add the Picture URL field
                'Filename': article.picture_filename,
                'Number of Phrases': article.phrasecount,
                'Has Money': article.hasmoney,
            }
            writer.writerow(row)
         


def main():
    variables_file = 'variables.ini'
    variables = read_variables_file(variables_file)
    time.sleep(5)
    query = variables["query"]
    sections = variables["sections"].split(',')
    months_to_search = variables["months_to_search"]
    new_query = QueryElements(query, months_to_search, sections)
    articles = new_query.get_articles()
    save_articles_to_csv(articles, "results.csv")
   

    for article in articles:
        print("Title:", article.title)
        print("Date:", article.date)
        print("Description:", article.description)
        print("Picture URL:", article.picture_url)
        print("filename: ", article.picture_filename)
        print("has money: ", article.hasmoney)
        print("number of phrases", article.phrasecount)
        print()
 


if __name__ == "__main__":
    main()
