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
    search_complete = pyqtSignal(list)
    citation_text_complete = pyqtSignal(list)
    citation_context_complete = pyqtSignal(list)
    
    def __init__(self, engine, file_path):
        super().__init__()
        self.engine = engine
        self.file_path = file_path
        self.translator = Translator(service_urls=['translate.google.com'])
        
    def run(self):
        paper_content = self.extract_paper_content(self.file_path)
        
        # Language detection
        detected_language = self.detect_language(paper_content)
        
        if detected_language == 'en':
            # If the content is already in English, search directly
            reference_papers = self.search_reference_papers(paper_content, num_pages=3)
        else:
            # If the content is in a different language, translate to English and search
            translated_content = self.translate_content(paper_content)
            reference_papers = self.search_reference_papers(translated_content, num_pages=3)
        
        self.search_complete.emit(reference_papers)
        
        citation_texts = self.extract_citation_text(reference_papers)
        self.citation_text_complete.emit(citation_texts)
        
        citation_contexts = self.extract_citation_contexts(paper_content, citation_texts)
        self.citation_context_complete.emit(citation_contexts)
    
    @staticmethod
    def extract_paper_content(file_path):
        document = Document(file_path)
        content = [paragraph.text for paragraph in document.paragraphs]
        return '\n'.join(content)
    
    @staticmethod
    def detect_language(text):
        detected = Translator().detect(text)
        return detected.lang
    
    def translate_content(self, text):
        translation = self.translator.translate(text, dest='en')
        return translation.text
    
    @staticmethod
    def fetch_search_results(url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
        except requests.exceptions.RequestException as e:
            print(f'Error occurred while fetching search results: {e}')
            return None
    
    @staticmethod
    def extract_paper_info(result):
        paper_title = result.find('h3', {'class': 'gs_rt'}).text.strip()
        paper_authors = result.find('div', {'class': 'gs_a'}).text.strip()
        paper_citations = result.find('div', {'class': 'gs_fl'}).text.strip()
        return f'{paper_title} - {paper_authors} ({paper_citations})'
    
    def search_reference_papers(self, query, num_pages=1):
        search_engine = {
            'Google Scholar': 'https://scholar.google.com/scholar?q={}',
            'PubMed': 'https://pubmed.ncbi.nlm.nih.gov/?term={}',
            'IEEE Xplore': 'https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={}',
            # Add other search engines
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
        
        # Sort the papers based on citations in descending order
        papers.sort(key=lambda paper: int(paper.split(" - ")[-1].split(" ")[0]), reverse=True)
        
        return papers
    
    def fetch_citation_text(self, reference_papers):
        citation_texts = []
        
        for paper_info in reference_papers:
            title, authors, citations = paper_info.split(" - ")
            search_query = f'"{title}"'
            
            search_engine = {
                'Google Scholar': 'https://scholar.google.com/scholar?q={}',
                'PubMed': 'https://pubmed.ncbi.nlm.nih.gov/?term={}',
                'IEEE Xplore': 'https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={}',
                # Add other search engines
            }
            
            engine_url = search_engine[self.engine]
            
            # Check if the content is in English or needs translation
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
    
    @staticmethod
    def extract_citation_text_from_results(search_results, paper_title):
        for result in search_results:
            title = result.find('h3', {'class': 'gs_rt'}).text.strip()
            if title == paper_title:
                citation_text = result.find('div', {'class': 'gs_fl'}).text.strip()
                return citation_text
        
        return None
    
    def extract_citation_contexts(self, paper_content, citation_texts):
        citation_contexts = []
        
        for citation_text in citation_texts:
            if citation_text:
                citation_context = self.extract_citation_context(paper_content, citation_text)
                citation_contexts.append(citation_context)
            else:
                citation_contexts.append(None)
        
        return citation_contexts
    
    @staticmethod
    def extract_citation_context(paper_content, citation_text):
        context = None
        citation_sentences = citation_text.split('. ')
        
        for sentence in citation_sentences:
            if sentence in paper_content:
                context = sentence
                break
        
        return context

class ReferenceCheckerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_engine = 'Google Scholar'
        self.translator = Translator()
        
        self.setWindowTitle('Reference Checker')
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        layout = QGridLayout(self.central_widget)
        
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit, 0, 0, 1, 2)
        
        browse_button = QPushButton('Browse')
        browse_button.clicked.connect(self.process_file)
        layout.addWidget(browse_button, 1, 0)
        
        search_button = QPushButton('Search')
        search_button.clicked.connect(self.start_search)
        layout.addWidget(search_button, 1, 1)
        
        engine_label = QLabel('Select a search engine:')
        layout.addWidget(engine_label, 2, 0)
        
        self.engine_combobox = QComboBox()
        self.engine_combobox.addItem('Google Scholar')
        self.engine_combobox.addItem('PubMed')
        self.engine_combobox.addItem('IEEE Xplore')
        # Add other search engines
        self.engine_combobox.currentTextChanged.connect(self.engine_selected)
        layout.addWidget(self.engine_combobox, 2, 1)
        
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(['Title', 'Authors', 'Citations', 'Citation Context'])
        layout.addWidget(self.tree_widget, 3, 0, 1, 2)
        
        self.show()
    
    def process_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select a file', '', 'Text Files (*.txt);;PDF Files (*.pdf);;Word Documents (*.docx)')
        if file_path:
            try:
                self.text_edit.clear()
                if file_path.endswith('.txt'):
                    with open(file_path, 'r', encoding='utf-8') as file:
                        paper_content = file.read()
                        self.text_edit.setPlainText(paper_content)
                elif file_path.endswith('.pdf'):
                    self.text_edit.setPlainText('Loading PDF...')
                    self.worker = ReferenceCheckerWorker(self.selected_engine, file_path)
                    self.worker.search_complete.connect(self.show_reference_papers)
                    self.worker.citation_text_complete.connect(self.show_citation_texts)
                    self.worker.citation_context_complete.connect(self.show_citation_contexts)
                    self.worker.start()
                elif file_path.endswith('.docx'):
                    self.text_edit.setPlainText('Loading Word document...')
                    self.worker = ReferenceCheckerWorker(self.selected_engine, file_path)
                    self.worker.search_complete.connect(self.show_reference_papers)
                    self.worker.citation_text_complete.connect(self.show_citation_texts)
                    self.worker.citation_context_complete.connect(self.show_citation_contexts)
                    self.worker.start()
                else:
                    self.text_edit.setPlainText('Unsupported file format.')
            except Exception as e:
                QMessageBox.critical(self, 'Error', str(e))
    
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
            QMessageBox.warning(self, 'Warning', 'No paper content to search.')
    
    def show_reference_papers(self, reference_papers):
        if reference_papers:
            for paper_info in reference_papers:
                title, authors, citations = paper_info.split(" - ")
                item = QTreeWidgetItem([title, authors, citations])
                self.tree_widget.addTopLevelItem(item)
        else:
            QMessageBox.information(self, 'Reference Papers', 'No reference papers found.')
    
    def show_citation_texts(self, citation_texts):
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            citation_text = citation_texts[i]
            
            if citation_text:
                item.setText(3, citation_text)
    
    def show_citation_contexts(self, citation_contexts):
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            citation_context = citation_contexts[i]
            
            if citation_context:
                item.setText(4, citation_context)
    
    def engine_selected(self, engine):
        self.selected_engine = engine

if __name__ == '__main__':
    app = QApplication(sys.argv)
    reference_checker = ReferenceCheckerGUI()
    sys.exit(app.exec_())
