import sys
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from googletrans import Translator
from summa import summarizer, keywords
import networkx as nx
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QFileDialog, QPushButton, QComboBox, QTextEdit, QMessageBox, QTreeWidget, QTreeWidgetItem, QGridLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from docx import Document


class ReferenceCheckerWorker(QThread):
    search_complete = pyqtSignal(list)  # 검색 완료 신호
    citation_text_complete = pyqtSignal(list)  # 인용문 텍스트 완료 신호
    citation_context_complete = pyqtSignal(list)  # 인용문 컨텍스트 완료 신호

    def __init__(self, engine, file_path):
        super().__init__()
        self.engine = engine
        self.file_path = file_path
        self.translator = Translator(service_urls=['translate.google.com'])

    def run(self):
        try:
            paper_content = self.extract_paper_content(self.file_path)

            # 언어 감지
            detected_language = self.detect_language(paper_content)

            if detected_language == 'en':
                # 영어인 경우, 직접 검색
                reference_papers = self.search_reference_papers(paper_content, num_pages=3)
            else:
                # 다른 언어인 경우, 영어로 번역 후 검색
                translated_content = self.translate_content(paper_content)
                reference_papers = self.search_reference_papers(translated_content, num_pages=3)

            self.search_complete.emit(reference_papers)  # 검색 완료 신호 전달

            citation_texts = self.extract_citation_text(reference_papers)
            self.citation_text_complete.emit(citation_texts)  # 인용문 텍스트 완료 신호 전달

            citation_contexts = self.extract_citation_contexts(paper_content, citation_texts)
            self.citation_context_complete.emit(citation_contexts)  # 인용문 컨텍스트 완료 신호 전달
        except Exception as e:
            print(f'Error occurred during processing: {e}')
            self.search_complete.emit([])  # 빈 리스트를 전달하여 검색 실패 신호 전달
            self.citation_text_complete.emit([])  # 빈 리스트를 전달하여 인용문 텍스트 실패 신호 전달
            self.citation_context_complete.emit([])  # 빈 리스트를 전달하여 인용문 컨텍스트 실패 신호 전달

    @staticmethod
    def extract_paper_content(file_path):
        try:
            if file_path.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as file:
                    paper_content = file.read()
            elif file_path.endswith('.pdf'):
                paper_content = self.extract_pdf_content(file_path)
            elif file_path.endswith('.docx'):
                paper_content = self.extract_docx_content(file_path)
            elif file_path.endswith('.hwp'):
                paper_content = self.extract_hwp_content(file_path)
            else:
                raise ValueError('Unsupported file format.')
            
            return paper_content
        except Exception as e:
            raise ValueError(f'Error occurred while extracting paper content: {e}')

    @staticmethod
    def extract_pdf_content(file_path):
        try:
            # PDF 파일을 텍스트로 변환하는 로직 추가
            # 반환된 텍스트를 paper_content 변수에 할당
            return paper_content
        except Exception as e:
            raise ValueError(f'Error occurred while extracting PDF content: {e}')

    @staticmethod
    def extract_docx_content(file_path):
        try:
            document = Document(file_path)
            content = [paragraph.text for paragraph in document.paragraphs]
            paper_content = '\n'.join(content)
            return paper_content
        except Exception as e:
            raise ValueError(f'Error occurred while extracting DOCX content: {e}')

    @staticmethod
    def extract_hwp_content(file_path):
        try:
            hwp_text_extractor = HwpTextExtractor(file_path)
            hwp_text_extractor.extract_text()
            paper_content = hwp_text_extractor.get_text()
            return paper_content
        except Exception as e:
            raise ValueError(f'Error occurred while extracting HWP content: {e}')

    @staticmethod
    def detect_language(text):
        try:
            detected = Translator().detect(text)
            return detected.lang
        except Exception as e:
            raise ValueError(f'Error occurred while detecting language: {e}')

    def translate_content(self, text):
        try:
            translation = self.translator.translate(text, dest='en')
            return translation.text
        except Exception as e:
            raise ValueError(f'Error occurred while translating content: {e}')

    @staticmethod
    def fetch_search_results(url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
        except requests.exceptions.RequestException as e:
            raise ValueError(f'Error occurred while fetching search results: {e}')

    @staticmethod
    def extract_paper_info(result):
        try:
            paper_title = result.find('h3', {'class': 'gs_rt'}).text.strip()
            paper_authors = result.find('div', {'class': 'gs_a'}).text.strip()
            paper_citations = result.find('div', {'class': 'gs_fl'}).text.strip()
            return f'{paper_title} - {paper_authors} ({paper_citations})'
        except Exception as e:
            raise ValueError(f'Error occurred while extracting paper info: {e}')

    def search_reference_papers(self, query, num_pages=1):
        try:
            search_engine = {
                'Google Scholar': 'https://scholar.google.com/scholar?q={}',
                'PubMed': 'https://pubmed.ncbi.nlm.nih.gov/?term={}',
                'IEEE Xplore': 'https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={}',
                # 다른 검색 엔진 추가
            }

            engine_url = search_engine[self.engine]
            base_url = engine_url.format(query)
            urls = [f'{base_url}&start={i*10}' for i in range(num_pages)]
            papers = []

            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = executor.map(self.fetch_search_results, urls)

                for result in results:
                    if result is None:
                        continue

                    search_results = result.find_all('div', {'class': 'gs_r gs_or gs_scl'})
                    for search_result in search_results:
                        paper_info = self.extract_paper_info(search_result)
                        papers.append(paper_info)

            # 인용 수를 기준으로 논문 정렬
            papers.sort(key=lambda paper: int(paper.split(" - ")[-1].split(" ")[0]), reverse=True)

            return papers
        except Exception as e:
            raise ValueError(f'Error occurred while searching reference papers: {e}')

    def fetch_citation_text(self, reference_papers):
        try:
            citation_texts = []

            for paper_info in reference_papers:
                title, authors, citations = paper_info.split(" - ")
                search_query = f'"{title}"'

                search_engine = {
                    'Google Scholar': 'https://scholar.google.com/scholar?q={}',
                    'PubMed': 'https://pubmed.ncbi.nlm.nih.gov/?term={}',
                    'IEEE Xplore': 'https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={}',
                    # 다른 검색 엔진 추가
                }

                engine_url = search_engine[self.engine]

                if self.detect_language(search_query) == 'en':
                    search_url = engine_url.format(search_query)
                else:
                    translated_query = self.translate_content(search_query)
                    search_url = engine_url.format(translated_query)

                search_results = self.fetch_search_results(search_url)

                if search_results:
                    citation_text = self.extract_citation_text_from_results(search_results, title)
                    citation_texts.append(citation_text)
                else:
                    citation_texts.append(None)

            return citation_texts
        except Exception as e:
            raise ValueError(f'Error occurred while fetching citation text: {e}')

    @staticmethod
    def extract_citation_text_from_results(search_results, paper_title):
        try:
            for result in search_results:
                title = result.find('h3', {'class': 'gs_rt'}).text.strip()
                if title == paper_title:
                    citation_text = result.find('div', {'class': 'gs_fl'}).text.strip()
                    return citation_text

            return None
        except Exception as e:
            raise ValueError(f'Error occurred while extracting citation text from results: {e}')

    def extract_citation_contexts(self, paper_content, citation_texts):
        try:
            citation_contexts = []

            for citation_text in citation_texts:
                if citation_text:
                    citation_context = self.extract_citation_context(paper_content, citation_text)
                    citation_contexts.append(citation_context)
                else:
                    citation_contexts.append(None)

            return citation_contexts
        except Exception as e:
            raise ValueError(f'Error occurred while extracting citation contexts: {e}')

    @staticmethod
    def extract_citation_context(paper_content, citation_text):
        try:
            context = None
            citation_sentences = citation_text.split('. ')

            for sentence in citation_sentences:
                if sentence in paper_content:
                    context = sentence
                    break

            return context
        except Exception as e:
            raise ValueError(f'Error occurred while extracting citation context: {e}')


class ReferenceCheckerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_engine = 'Google Scholar'
        self.translator = Translator()

        self.setWindowTitle('Reference Checker')
        self.setGeometry(200, 200, 800, 600)  # 창 크기 조정

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QGridLayout(self.central_widget)

        self.text_edit = QTextEdit()
        self.layout.addWidget(self.text_edit, 0, 0, 1, 2)

        browse_button = QPushButton('파일 선택')
        browse_button.clicked.connect(self.process_file)
        self.layout.addWidget(browse_button, 1, 0)

        search_button = QPushButton('검색')
        search_button.clicked.connect(self.start_search)
        self.layout.addWidget(search_button, 1, 1)

        engine_label = QLabel('검색 엔진 선택:')
        self.layout.addWidget(engine_label, 2, 0)

        self.engine_combobox = QComboBox()
        self.engine_combobox.addItem('Google Scholar')
        self.engine_combobox.addItem('PubMed')
        self.engine_combobox.addItem('IEEE Xplore')
        # 다른 검색 엔진 추가
        self.engine_combobox.currentTextChanged.connect(self.engine_selected)
        self.layout.addWidget(self.engine_combobox, 2, 1)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(['제목', '저자', '인용 수', '인용문 텍스트', '인용문 컨텍스트'])
        self.layout.addWidget(self.tree_widget, 3, 0, 1, 2)

        self.show()

    def process_file(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, '파일 선택', '', '텍스트 파일 (*.txt);;PDF 파일 (*.pdf);;Word 문서 (*.docx);;HWP 파일 (*.hwp)')
            if file_path:
                self.text_edit.clear()
                if file_path.endswith('.txt'):
                    with open(file_path, 'r', encoding='utf-8') as file:
                        paper_content = file.read()
                        self.text_edit.setPlainText(paper_content)
                elif file_path.endswith('.pdf'):
                    self.text_edit.setPlainText('PDF 로딩 중...')
                    self.worker = ReferenceCheckerWorker(self.selected_engine, file_path)
                    self.worker.search_complete.connect(self.show_reference_papers)
                    self.worker.citation_text_complete.connect(self.show_citation_texts)
                    self.worker.citation_context_complete.connect(self.show_citation_contexts)
                    self.worker.start()
                elif file_path.endswith('.docx'):
                    self.text_edit.setPlainText('Word 문서 로딩 중...')
                    self.worker = ReferenceCheckerWorker(self.selected_engine, file_path)
                    self.worker.search_complete.connect(self.show_reference_papers)
                    self.worker.citation_text_complete.connect(self.show_citation_texts)
                    self.worker.citation_context_complete.connect(self.show_citation_contexts)
                    self.worker.start()
                elif file_path.endswith('.hwp'):
                    self.text_edit.setPlainText('HWP 파일 로딩 중...')
                    self.worker = ReferenceCheckerWorker(self.selected_engine, file_path)
                    self.worker.search_complete.connect(self.show_reference_papers)
                    self.worker.citation_text_complete.connect(self.show_citation_texts)
                    self.worker.citation_context_complete.connect(self.show_citation_contexts)
                    self.worker.start()
                else:
                    self.text_edit.setPlainText('지원되지 않는 파일 형식입니다.')
        except Exception as e:
            QMessageBox.critical(self, '오류', str(e))

    def start_search(self):
        paper_content = self.text_edit.toPlainText()
        if paper_content:
            self.tree_widget.clear()
            self.worker = ReferenceCheckerWorker(self.selected_engine, paper_content)
            self.worker.search_complete.connect(self.show_reference_papers)
            self.worker.citation_text_complete.connect(self.show_citation_texts)
            self.worker.citation_context_complete.connect(self.show_citation_contexts)
            self.worker.start()
        else:
            QMessageBox.warning(self, '경고', '검색할 논문 내용이 없습니다.')

    def show_reference_papers(self, reference_papers):
        try:
            if reference_papers:
                for paper_info in reference_papers:
                    title, authors, citations = paper_info.split(" - ")
                    item = QTreeWidgetItem([title, authors, citations])
                    self.tree_widget.addTopLevelItem(item)
            else:
                QMessageBox.information(self, '참조 논문', '참조 논문이 없습니다.')
        except Exception as e:
            QMessageBox.critical(self, '오류', str(e))

    def show_citation_texts(self, citation_texts):
        try:
            for i in range(self.tree_widget.topLevelItemCount()):
                item = self.tree_widget.topLevelItem(i)
                citation_text = citation_texts[i]

                if citation_text:
                    item.setText(3, citation_text)
        except Exception as e:
            QMessageBox.critical(self, '오류', str(e))

    def show_citation_contexts(self, citation_contexts):
        try:
            for i in range(self.tree_widget.topLevelItemCount()):
                item = self.tree_widget.topLevelItem(i)
                citation_context = citation_contexts[i]

                if citation_context:
                    item.setText(4, citation_context)
        except Exception as e:
            QMessageBox.critical(self, '오류', str(e))

    def engine_selected(self, engine):
        self.selected_engine = engine


if __name__ == '__main__':
    app = QApplication(sys.argv)
    reference_checker = ReferenceCheckerGUI()
    sys.exit(app.exec_())
