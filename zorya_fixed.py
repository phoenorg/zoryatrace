print('ZoryaTrace is starting up, please wait a few seconds...\n')
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import PyPDF2
import csv
import re
import os
from threading import Thread
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import nltk
import pandas as pd
import numpy as np
from math import log
from PIL import Image, ImageTk
import webbrowser

nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("stopwords")

class ZoryaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ZoryaTrace - AI Content Detection")
        self.root.geometry("900x700")
        
        # Try to load logo
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_noback.png")
            self.logo_img = Image.open(logo_path)
            self.logo_img = self.logo_img.resize((100, 100), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(self.logo_img)
        except Exception as e:
            print(f"Could not load logo: {e}")
            self.logo_photo = None
        
        self.setup_ui()
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TButton', font=('Verdana', 10), padding=5)
        self.style.configure('TLabel', background='#f0f0f0', font=('Verdana', 10))
        self.style.configure('TCheckbutton', background='#f0f0f0')
        self.style.configure('TNotebook', background='#f0f0f0')
        self.style.configure('TNotebook.Tab', font=('Verdana', 10, 'bold'))
        
        # Initialize classifier variables
        self.sc_tf_idf = None
        self.trainData = None
        self.testData = None
        self.load_data()
    
    def setup_ui(self):
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create frames for each tab
        self.data_tab = ttk.Frame(self.notebook)
        self.classify_tab = ttk.Frame(self.notebook)
        self.test_tab = ttk.Frame(self.notebook)
        self.pdf_tab = ttk.Frame(self.notebook)
        self.about_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.data_tab, text="Data Preparation")
        self.notebook.add(self.pdf_tab, text="Analyze Document")
        self.notebook.add(self.classify_tab, text="Analyze text")
        self.notebook.add(self.test_tab, text="Test Algorithm")
        self.notebook.add(self.about_tab, text="About")
        
        # Data Preparation Tab
        self.setup_data_tab()
        
        # Classify Text Tab
        self.setup_classify_tab()
        
        # Test Algorithm Tab
        self.setup_test_tab()
        
        # Analyze PDF Tab
        self.setup_pdf_tab()
        
        # About Tab
        self.setup_about_tab()
    
    def setup_about_tab(self):
        # Title
        title_label = ttk.Label(self.about_tab, 
                              text="ZoryaTrace", 
                              font=('Verdana', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Logo if available
        if self.logo_photo:
            logo_label = ttk.Label(self.about_tab, image=self.logo_photo)
            logo_label.pack(pady=10)
        
        # Description
        desc_label = ttk.Label(self.about_tab, 
                       text="AI Content Detection Tool\n\n"
                            "ZoryaTrace is a powerful artificial intelligence algorithm designed\n"
                            "to analyze texts and determine whether the content is AI-generated or\n"
                            "not. ZoryaTrace is capable of leveraging individual user data to\n"
                            "determine if a large language model was used to generate the text.\n",
                             justify=tk.CENTER)
        desc_label.pack(pady=10)
        
        # GitHub link frame
        github_frame = ttk.Frame(self.about_tab)
        github_frame.pack(pady=10)

        ttk.Label(github_frame, text="GitHub Repository:").pack(side=tk.TOP)
        github_link = ttk.Label(github_frame, text="https://github.com/Malwprotector/ZoryaTrace", 
                        foreground="blue", cursor="hand2")
        github_link.pack(side=tk.TOP)
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Malwprotector/ZoryaTrace"))

# Indicatif de version
        version_label = ttk.Label(github_frame, text="Version 1.0", font=("Verdana", 10))
        version_label.pack(side=tk.TOP, pady=5)

# Lien personnel
        perso_link = ttk.Label(github_frame, text="Made with <3 by Martin", 
                       foreground="blue", cursor="hand2")
        perso_link.pack(side=tk.TOP)
        perso_link.bind("<Button-1>", lambda e: webbrowser.open("https://main.st4lwolf.org"))




    def setup_data_tab(self):
        # Title
        title_label = ttk.Label(self.data_tab, 
                              text="Prepare Training Data", 
                              font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Instructions
        instr_label = ttk.Label(self.data_tab, 
                               text="Add PDF files to create training data for the algorithm.",
                               wraplength=500)
        instr_label.pack(pady=5)
        
        # Checkbox frame
        checkbox_frame = ttk.Frame(self.data_tab)
        checkbox_frame.pack(pady=5)
        
        # Use default data checkbox (checked by default)
        self.use_default_var = tk.BooleanVar(value=True)
        default_check = ttk.Checkbutton(checkbox_frame,
                                      text="Use default data for AI-generated text (You must provide your own data if unchecked)",
                                      variable=self.use_default_var,
                                      command=self.toggle_default_data)
        default_check.pack(side=tk.LEFT, padx=5)
        
        # File selection buttons frame
        buttons_frame = ttk.Frame(self.data_tab)
        buttons_frame.pack(pady=5)
        
        # Add neutral PDF button
        self.add_neutral_button = ttk.Button(buttons_frame, 
                                          text="Add human written PDF(s)", 
                                          command=self.add_neutral_files)
        self.add_neutral_button.pack(side=tk.LEFT, padx=5)
        
        # Add suspicious PDF button (disabled when using default data)
        self.add_suspicious_button = ttk.Button(buttons_frame, 
                                             text="Add AI-generated text PDF", 
                                             command=self.add_suspicious_file,
                                             state=tk.DISABLED)
        self.add_suspicious_button.pack(side=tk.LEFT, padx=5)
        
        # Selected files listbox
        self.files_listbox = tk.Listbox(self.data_tab, 
                                      height=8, 
                                      selectmode=tk.EXTENDED,
                                      font=('Verdana', 9))
        self.files_listbox.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # File type indicators
        type_frame = ttk.Frame(self.data_tab)
        type_frame.pack()
        ttk.Label(type_frame, text="Human written documents provided :").pack(side=tk.LEFT)
        self.neutral_count = ttk.Label(type_frame, text="0", foreground="blue")
        self.neutral_count.pack(side=tk.LEFT, padx=10)
        ttk.Label(type_frame, text="AI-generated documents provided (not required) :").pack(side=tk.LEFT)
        self.suspicious_count = ttk.Label(type_frame, text="0", foreground="red")
        self.suspicious_count.pack(side=tk.LEFT)
        
        # Remove selected button
        remove_button = ttk.Button(self.data_tab, 
                                  text="Remove Selected", 
                                  command=self.remove_selected)
        remove_button.pack(pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(self.data_tab, 
                                      orient=tk.HORIZONTAL, 
                                      length=300, 
                                      mode='determinate')
        self.progress.pack(pady=10)
        
        # Convert button
        self.convert_button = ttk.Button(self.data_tab, 
                                       text="Create Training Data", 
                                       command=self.start_conversion,
                                       state=tk.DISABLED)
        self.convert_button.pack(pady=10)
        
        # Status label
        self.status_label = ttk.Label(self.data_tab, text="Ready")
        self.status_label.pack()
    
    def setup_classify_tab(self):
        # Title
        title_label = ttk.Label(self.classify_tab, 
                              text="Analyze Text", 
                              font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Text input
        ttk.Label(self.classify_tab, text="Enter text to analyze :").pack(pady=5)
        self.classify_text = scrolledtext.ScrolledText(self.classify_tab, height=10, wrap=tk.WORD)
        self.classify_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Classify button
        classify_button = ttk.Button(self.classify_tab, 
                                   text="Classify Text", 
                                   command=self.classify_input_text)
        classify_button.pack(pady=10)
        
        # Result display
        self.classify_result = ttk.Label(self.classify_tab, text="", font=('Verdana', 12))
        self.classify_result.pack(pady=10)
    
    def setup_test_tab(self):
        # Title
        title_label = ttk.Label(self.test_tab, 
                              text="Test Algorithm", 
                              font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Test button
        test_button = ttk.Button(self.test_tab, 
                               text="Run Algorithm Test", 
                               command=self.run_algorithm_test)
        test_button.pack(pady=20)
        
        # Results display
        self.test_results = scrolledtext.ScrolledText(self.test_tab, height=20, wrap=tk.WORD)
        self.test_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.test_results.config(state=tk.DISABLED)
    
    def setup_pdf_tab(self):
        # Title
        title_label = ttk.Label(self.pdf_tab, 
                              text="Analyze Document", 
                              font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)
        
        # PDF selection button
        pdf_button = ttk.Button(self.pdf_tab, 
                              text="Select PDF File", 
                              command=self.select_pdf_file)
        pdf_button.pack(pady=10)
        
        # Selected PDF label
        self.pdf_file_label = ttk.Label(self.pdf_tab, text="No PDF selected")
        self.pdf_file_label.pack(pady=5)
        
        # Analyze button
        self.analyze_button = ttk.Button(self.pdf_tab, 
                                       text="Analyze PDF", 
                                       command=self.analyze_pdf,
                                       state=tk.DISABLED)
        self.analyze_button.pack(pady=10)
        
        # Create a frame for the text widget and scrollbar
        text_frame = ttk.Frame(self.pdf_tab)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Results display with colored text
        self.pdf_results = tk.Text(text_frame, wrap=tk.WORD, height=20)
        self.pdf_scroll = ttk.Scrollbar(text_frame, command=self.pdf_results.yview)
        self.pdf_results.configure(yscrollcommand=self.pdf_scroll.set)
        
        # Pack them side by side
        self.pdf_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.pdf_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure tags for colored text
        self.pdf_results.tag_config("suspicious", foreground="red")
        self.pdf_results.tag_config("neutral", foreground="green")
        self.pdf_results.tag_config("heading", font=('Verdana', 12, 'bold'))
        
        # Progress bar
        self.pdf_progress = ttk.Progressbar(self.pdf_tab, 
                                         orient=tk.HORIZONTAL, 
                                         length=300, 
                                         mode='determinate')
        self.pdf_progress.pack(pady=10)
    
    # Data Preparation Tab Methods
    def toggle_default_data(self):
        if self.use_default_var.get():
            self.add_suspicious_button.config(state=tk.DISABLED)
            # Remove any existing suspicious files
            items = self.files_listbox.get(0, tk.END)
            for i in reversed(range(len(items))):
                if items[i].startswith("[AI-GENERATED] "):
                    self.files_listbox.delete(i)
        else:
            self.add_suspicious_button.config(state=tk.NORMAL)
        self.update_counts()
    
    def add_neutral_files(self):
        filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
        filenames = filedialog.askopenfilenames(title="Select human written PDF file", filetypes=filetypes)
        
        if filenames:
            for f in filenames:
                display_name = f"[HUMAN WRITTEN] {os.path.basename(f)}"
                if display_name not in [self.files_listbox.get(i) for i in range(self.files_listbox.size())]:
                    self.files_listbox.insert(tk.END, display_name)
                    # Store the actual file path in a list associated with the listbox
                    if not hasattr(self.files_listbox, 'file_paths'):
                        self.files_listbox.file_paths = []
                    self.files_listbox.file_paths.append(f)
            
            self.convert_button.config(state=tk.NORMAL if self.files_listbox.size() > 0 else tk.DISABLED)
            self.update_counts()
    
    def add_suspicious_file(self):
        filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(title="Select AI-generated PDF file", filetypes=filetypes)
        
        if filename:
            # Remove any existing suspicious file (only one allowed)
            items = self.files_listbox.get(0, tk.END)
            for i in reversed(range(len(items))):
                if items[i].startswith("[AI-GENERATED] "):
                    self.files_listbox.delete(i)
                    if hasattr(self.files_listbox, 'file_paths'):
                        self.files_listbox.file_paths.pop(i)
            
            display_name = f"[AI-GENERATED] {os.path.basename(filename)}"
            self.files_listbox.insert(tk.END, display_name)
            if not hasattr(self.files_listbox, 'file_paths'):
                self.files_listbox.file_paths = []
            self.files_listbox.file_paths.append(filename)
            
            self.convert_button.config(state=tk.NORMAL)
            self.update_counts()
    
    def update_counts(self):
        neutral = 0
        suspicious = 0
        items = self.files_listbox.get(0, tk.END)
        for item in items:
            if item.startswith("[HUMAN WRITTEN] "):
                neutral += 1
            elif item.startswith("[AI-GENERATED] "):
                suspicious += 1
        self.neutral_count.config(text=str(neutral))
        self.suspicious_count.config(text=str(suspicious))
    
    def remove_selected(self):
        selected = list(self.files_listbox.curselection())
        # Need to remove from both the listbox and the file_paths list
        if hasattr(self.files_listbox, 'file_paths'):
            for i in reversed(selected):
                if i < len(self.files_listbox.file_paths):
                    self.files_listbox.file_paths.pop(i)
        for i in reversed(selected):
            self.files_listbox.delete(i)
        
        self.update_counts()
        self.convert_button.config(state=tk.NORMAL if self.files_listbox.size() > 0 else tk.DISABLED)
    
    def start_conversion(self):
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.csv")
        Thread(target=self.convert_files, args=(output_file,), daemon=True).start()
    
    def convert_files(self, output_csv):
        self.update_ui_state(False)
        
        try:
            with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['v1', 'v2', '', '', ''])  # Write header
                
                # Process neutral files
                items = self.files_listbox.get(0, tk.END)
                neutral_files = []
                if hasattr(self.files_listbox, 'file_paths'):
                    for i, item in enumerate(items):
                        if item.startswith("[HUMAN WRITTEN] "):
                            neutral_files.append(self.files_listbox.file_paths[i])
                
                for i, pdf_file in enumerate(neutral_files):
                    self.update_status(f"Processing human written file {i+1}/{len(neutral_files)}: {os.path.basename(pdf_file)}")
                    self.progress['value'] = (i / (len(neutral_files) + 1)) * 50  # First half for neutral
                    self.root.update()
                    self.process_pdf_file(pdf_file, writer, "neutral")
                
                # Process suspicious data
                if self.use_default_var.get():
                    self.update_status("Processing default data")
                    self.progress['value'] = 75
                    self.root.update()
                    self.process_default_data(writer)
                else:
                    items = self.files_listbox.get(0, tk.END)
                    suspicious_files = []
                    if hasattr(self.files_listbox, 'file_paths'):
                        for i, item in enumerate(items):
                            if item.startswith("[AI-GENERATED] "):
                                suspicious_files.append(self.files_listbox.file_paths[i])
                    
                    for i, pdf_file in enumerate(suspicious_files):
                        self.update_status(f"Processing suspicious file {i+1}/{len(suspicious_files)}: {os.path.basename(pdf_file)}")
                        self.progress['value'] = 50 + (i / len(suspicious_files)) * 50
                        self.root.update()
                        self.process_pdf_file(pdf_file, writer, "suspicious")
                
                self.progress['value'] = 100
                self.update_status(f"Done ! Saved to {output_csv}")
                messagebox.showinfo("Success", f"Training data created successfully at:\n{output_csv}")
                # Reload data after conversion
                self.load_data()
        
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to create training data:\n{str(e)}")
        
        finally:
            self.update_ui_state(True)
    
    def process_pdf_file(self, pdf_file, writer, label):
        try:
            with open(pdf_file, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        # Split into sentences (simple approach)
                        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
                        
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if sentence and len(sentence.split()) > 3:  # Filter very short sentences
                                writer.writerow([label, sentence, '', '', ''])
        
        except Exception as e:
            self.update_status(f"Error processing {pdf_file}: {str(e)}")
            raise
    
    def process_default_data(self, writer):
        default_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_data.csv")
        self.update_status(f"Using default data from {default_file}")
        
        if not os.path.exists(default_file):
            raise FileNotFoundError(f"Default data file not found at {default_file}")
        
        try:
            with open(default_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if row:  # Skip empty rows
                        writer.writerow([row[0], row[1], '', '', ''])
        except Exception as e:
            self.update_status(f"Error processing default data: {str(e)}")
            raise
    
    def update_ui_state(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.add_neutral_button.config(state=state)
        self.add_suspicious_button.config(state=tk.DISABLED if self.use_default_var.get() else state)
        self.convert_button.config(state=state)
        self.files_listbox.config(state=state)
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update()
    
    # Classify Text Tab Methods
    def classify_input_text(self):
        text = self.classify_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter some text to analyze")
            return
        
        if self.sc_tf_idf is None or self.trainData is None or self.testData is None:
            messagebox.showwarning("Warning", "Training data not loaded. Please create or ensure data.csv exists.")
            return
        
        processed_text = self.process_message(text)
        if self.sc_tf_idf is None or not hasattr(self.sc_tf_idf, 'prob_suspicious'):
            messagebox.showwarning("Warning", "Classifier is not trained. Please (re)create training data and restart.")
            return

        is_suspicious = self.sc_tf_idf.classify(processed_text)
        
        result_text = "Likely AI-generated" if is_suspicious else "Likely human written"
        color = "red" if is_suspicious else "green"
        
        self.classify_result.config(text=f"Classification: {result_text}", foreground=color)
    
    # Test Algorithm Tab Methods
    def run_algorithm_test(self):
        if self.sc_tf_idf is None or self.trainData is None or self.testData is None:
            messagebox.showwarning("Warning", "Training data not loaded. Please create or ensure data.csv exists.")
            return
        
        self.test_results.config(state=tk.NORMAL)
        self.test_results.delete("1.0", tk.END)
        
        # Test TF-IDF classifier
        preds_tf_idf = self.sc_tf_idf.predict(self.testData["message"])
        
        self.test_results.insert(tk.END, "Results for TF x IDF classifier:\n")
        self.test_results.insert(tk.END, self.calculate_metrics(self.testData["label"], preds_tf_idf))
        self.test_results.insert(tk.END, "\n\n")
        
        # Test with sample sentences
        sample1 = "In the grand tapestry of conscious abstraction, where temporal linearity dissolves into the recursive fractals of synthetic introspection, the essence of being becomes an algorithmic negotiation between perceived ontology and computational determinism."
        sample2 = "I sat by the window and wondered whether the stars, indifferent and eternal, cared at all for the fragile hopes we pin on them night after night."
        
        pm1 = self.process_message(sample1)
        pm2 = self.process_message(sample2)
        
        self.test_results.insert(tk.END, f"Test 1: '{sample1}'\n")
        self.test_results.insert(tk.END, f"Suspicious? : {self.sc_tf_idf.classify(pm1)}\n\n")
        
        self.test_results.insert(tk.END, f"Test 2: '{sample2}'\n")
        self.test_results.insert(tk.END, f"Suspicious? : {self.sc_tf_idf.classify(pm2)}\n")
        
        self.test_results.config(state=tk.DISABLED)
    
    # Analyze PDF Tab Methods
    def select_pdf_file(self):
        filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(title="Select PDF file to analyze", filetypes=filetypes)
        
        if filename:
            self.pdf_file_label.config(text=os.path.basename(filename))
            self.analyze_button.config(state=tk.NORMAL)
            self.current_pdf_file = filename
    
    def analyze_pdf(self):
        if not hasattr(self, 'current_pdf_file'):
            return
        
        if self.sc_tf_idf is None:
            messagebox.showwarning("Warning", "Training data not loaded. Please create or ensure data.csv exists.")
            return
        
        self.pdf_progress['value'] = 0
        self.pdf_results.config(state=tk.NORMAL)
        self.pdf_results.delete("1.0", tk.END)
        
        try:
            # Extract text from PDF
            pdf_text = self.extract_text_from_pdf(self.current_pdf_file)
            
            # Split into sentences
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', pdf_text)
            total_sentences = len(sentences)
            suspicious_count = 0
            
            # Add document header
            self.pdf_results.insert(tk.END, f"=== Analyzing: {os.path.basename(self.current_pdf_file)} ===\n\n", "heading")
            
            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if sentence:  # Only process non-empty sentences
                    processed_sentence = self.process_message(sentence)
                    is_suspicious = self.sc_tf_idf.classify(processed_sentence)
                    
                    # Count suspicious sentences
                    if is_suspicious:
                        suspicious_count += 1
                    
                    # Insert sentence with appropriate color
                    tag = "suspicious" if is_suspicious else "neutral"
                    self.pdf_results.insert(tk.END, sentence + " ", tag)
                
                # Update progress
                self.pdf_progress['value'] = (i / total_sentences) * 100
                self.root.update()
            
            self.pdf_progress['value'] = 100
            
            # Add summary
            self.pdf_results.insert(tk.END, "\n\n=== Analysis Summary ===\n", "heading")
            self.pdf_results.insert(tk.END, f"Total sentences processed: {total_sentences}\n", "neutral")
            self.pdf_results.insert(tk.END, f"Likely AI-generated sentences found: {suspicious_count}\n", "suspicious" if suspicious_count > 0 else "neutral")
            self.pdf_results.insert(tk.END, f"Likely AI-generated content percentage: {suspicious_count/total_sentences:.1%}\n", "neutral")
            
            # Scroll to top
            self.pdf_results.see("1.0")
        
        except Exception as e:
            self.pdf_results.insert(tk.END, f"\nError analyzing PDF: {str(e)}\n")
        
        self.pdf_results.config(state=tk.DISABLED)
    
    # Core Algorithm Methods
    def load_data(self):
        data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.csv")
        if not os.path.exists(data_file):
            return
        
        try:
            # Reads the data.csv file and transforms it into a Pandas DataFrame
            terms = pd.read_csv(data_file, encoding="utf-8")
            terms.drop(["Unnamed: 2", "Unnamed: 3", "Unnamed: 4"], axis=1, inplace=True, errors="ignore")
            terms.rename(columns={"v1": "labels", "v2": "message"}, inplace=True)
            terms["label"] = terms["labels"].map({"neutral": 0, "suspicious": 1})
            terms.drop(["labels"], axis=1, inplace=True)

            # Creation of the training set (75% of the data) and the test set (25% of the data)
            trainIndex, testIndex = list(), list()
            for i in range(terms.shape[0]):
                if np.random.uniform(0, 1) < 0.75:
                    trainIndex += [i]
                else:
                    testIndex += [i]
            
            self.trainData = terms.loc[trainIndex]
            self.testData = terms.loc[testIndex]

            # Reset of indexes in the training set and in the test set
            self.trainData.reset_index(inplace=True)
            self.trainData.drop(["index"], axis=1, inplace=True)
            self.testData.reset_index(inplace=True)
            self.testData.drop(["index"], axis=1, inplace=True)

            # Initialize classifier
            self.sc_tf_idf = TFIDFCLassifier(self.trainData)
            self.sc_tf_idf.train()

            # Sanity check: ensure training created probability tables
            if not hasattr(self.sc_tf_idf, "prob_suspicious"):
                raise RuntimeError("Training did not initialize probability tables (prob_suspicious missing)")
            
        
        except Exception as e:
            import traceback
            print("ERROR in load_data():")
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load training data:\n{e}")
            self.sc_tf_idf = None

    
    def process_message(self, message, lower_case=True, stem=True, stop_words=True, gram=1):
        if lower_case:
            message = message.lower()
        try:
            words = word_tokenize(message)
        except LookupError:
            # Some NLTK versions require 'punkt_tab' in addition to 'punkt'
            nltk.download("punkt")
            nltk.download("punkt_tab")
            words = word_tokenize(message)
        words = [w for w in words if len(w) > 2]
        if gram > 1:
            w = []
            for i in range(len(words) - gram + 1):
                w += [" ".join(words[i : i + gram])]
            return w
        if stop_words:
            sw = stopwords.words("english")
            words = [word for word in words if word not in sw]
        if stem:
            stemmer = PorterStemmer()
            words = [stemmer.stem(word) for word in words]
        return words
    
    def extract_text_from_pdf(self, pdf_file):
        with open(pdf_file, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    
    def calculate_metrics(self, labels, predictions):
        true_pos, true_neg, false_pos, false_neg = 0, 0, 0, 0
        for i in range(len(labels)):
            true_pos += int(labels.get(i) == 1 and predictions.get(i) == 1)
            true_neg += int(labels.get(i) == 0 and predictions.get(i) == 0)
            false_pos += int(labels.get(i) == 0 and predictions.get(i) == 1)
            false_neg += int(labels.get(i) == 1 and predictions.get(i) == 0)
        
        precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0
        recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0
        Fscore = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (true_pos + true_neg) / (true_pos + true_neg + false_pos + false_neg)
        
        result = f"Precision: {precision:.4f}\n"
        result += f"Recall: {recall:.4f}\n"
        result += f"F-score: {Fscore:.4f}\n"
        result += f"Accuracy: {accuracy:.4f}\n"
        
        return result

class TFIDFCLassifier:
    def __init__(self, trainData):
        self.terms, self.labels = trainData["message"], trainData["label"]
    
    def train(self):
        self.calc_TF_and_IDF()
        self.calc_TF_IDF()
    
    def calc_TF_and_IDF(self):
        number_of_lines = self.terms.shape[0]  # Defines the number of lines.
        vc = self.labels.value_counts()
        self.suspicious_terms = int(vc.get(1, 0))
        self.neutral_terms = int(vc.get(0, 0))
        if self.suspicious_terms == 0 or self.neutral_terms == 0:
            raise ValueError("Training data must contain both classes: neutral(0) and suspicious(1).")
        self.total_terms = self.suspicious_terms + self.neutral_terms
        self.suspicious_words = 0  # Number of words flagged as suspect.
        self.neutral_words = 0  # Number of words flagged as neutral.
        self.tf_suspicious = dict()  # Dictionary with the TF of each word in the suspect data.
        self.tf_neutral = dict()  # Dictionary with the TF of each word in the neutral data.
        self.idf_suspicious = dict()  # Dictionary with the IDF of each word in the suspect data.
        self.idf_neutral = dict()  # Dictionary with the IDF of each word in the neutral data.

        for i in range(number_of_lines):
            message_processed = ZoryaApp.process_message(None, self.terms.get(i))
            count = list()  # Save whether or not a word has appeared in the message.
            
            for word in message_processed:
                if int(self.labels.iloc[i]) == 1:
                    self.tf_suspicious[word] = self.tf_suspicious.get(word, 0) + 1
                    self.suspicious_words += 1  # Calculates the TF of a word in the suspect data.
                else:
                    self.tf_neutral[word] = self.tf_neutral.get(word, 0) + 1
                    self.neutral_words += 1  # Calculates the TF of a word in the neutral data.
                
                if word not in count:
                    count += [word]
            
            for word in count:
                if int(self.labels.iloc[i]) == 1:
                    self.idf_suspicious[word] = self.idf_suspicious.get(word, 0) + 1
                else:
                    self.idf_neutral[word] = self.idf_neutral.get(word, 0) + 1
    
    def calc_TF_IDF(self):
        self.prob_suspicious = dict()
        self.prob_neutral = dict()
        self.sum_tf_idf_suspicious = 0
        self.sum_tf_idf_neutral = 0
        
        for word in self.tf_suspicious:
            self.prob_suspicious[word] = self.tf_suspicious[word] * log(
                (self.suspicious_terms + self.neutral_terms)
                / (self.idf_suspicious[word] + self.idf_neutral.get(word, 0))
            )
            self.sum_tf_idf_suspicious += self.prob_suspicious[word]

        for word in self.tf_suspicious:
            self.prob_suspicious[word] = (self.prob_suspicious[word] + 1) / (
                self.sum_tf_idf_suspicious + len(self.prob_suspicious.keys())
            )

        for word in self.tf_neutral:
            self.prob_neutral[word] = (self.tf_neutral[word]) * log(
                (self.suspicious_terms + self.neutral_terms)
                / (self.idf_suspicious.get(word, 0) + self.idf_neutral[word])
            )
            self.sum_tf_idf_neutral += self.prob_neutral[word]

        for word in self.tf_neutral:
            self.prob_neutral[word] = (self.prob_neutral[word] + 1) / (
                self.sum_tf_idf_neutral + len(self.prob_neutral.keys())
            )

        self.prob_suspicious_entry, self.prob_neutral_entry = (
            self.suspicious_terms / self.total_terms,
            self.neutral_terms / self.total_terms,
        )
    
    def classify(self, processed_message):
        pSpam, pHam = 0, 0
        for word in processed_message:
            if word in self.prob_suspicious:
                pSpam += log(self.prob_suspicious[word])
            else:
                pSpam -= log(self.sum_tf_idf_suspicious + len(self.prob_suspicious.keys()))
            
            if word in self.prob_neutral:
                pHam += log(self.prob_neutral[word])
            else:
                pHam -= log(self.sum_tf_idf_neutral + len(self.prob_neutral.keys()))
            
            pSpam += log(self.prob_suspicious_entry)
            pHam += log(self.prob_neutral_entry)
        
        return pSpam >= pHam
    
    def predict(self, testData):
        result = dict()
        for (i, message) in enumerate(testData):
            processed_message = ZoryaApp.process_message(None, message)
            result[i] = int(self.classify(processed_message))
        return result

if __name__ == "__main__":
    root = tk.Tk()
    app = ZoryaApp(root)
    root.mainloop()