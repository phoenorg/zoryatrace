#!/usr/bin/env python3
"""ZoryaTrace - AI Content Detection

Refactor notes (2025-12):
- Robust training: prevents half-initialized classifiers (prob_* missing).
- Fast tokenization option (regex) to keep training under ~30s on typical laptops.
- Automatic subsampling to cap training size.
- Stratified train/test split.
- Background training thread to keep Tkinter responsive.
- NLTK resources: punkt + punkt_tab + stopwords.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import PyPDF2
import csv
import re
import os
from threading import Thread
from math import log
from PIL import Image, ImageTk
import webbrowser

import pandas as pd
import numpy as np

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

print('ZoryaTrace is starting up, please wait a few seconds...\n')

# ----------------------------
# Configuration (performance)
# ----------------------------
RANDOM_SEED = 42
TRAIN_SPLIT = 0.75  # 75% train, 25% test

# Keep training under ~30s by capping how many examples are used.
# You can tune these values.
TRAIN_MAX_TOTAL = 3000
TRAIN_MAX_SUSPICIOUS = 2000

# Text preprocessing knobs
USE_FAST_TOKENIZER = True   # regex tokenizer (faster than NLTK)
USE_STEMMING = False        # stemming slows training
STOPWORDS_LANGUAGE = 'english'

# Regex tokenizer: keep words >=3 chars, including accented letters.
TOKEN_REGEX = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ']{3,}")


def ensure_nltk_resources():
    """Download NLTK resources required by this app."""
    try:
        nltk.download('punkt', quiet=True)
        # Some NLTK versions require 'punkt_tab' in addition to 'punkt'
        nltk.download('punkt_tab', quiet=True)
        nltk.download('stopwords', quiet=True)
    except Exception as e:
        # Do not crash; we'll fallback to regex tokenizer if possible
        print(f"Warning: NLTK resource download failed: {e}")


def fast_tokenize(text: str):
    return TOKEN_REGEX.findall(text.lower())


class ZoryaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ZoryaTrace - AI Content Detection")
        self.root.geometry("900x700")

        ensure_nltk_resources()

        # Precompute stopwords + stemmer once
        try:
            self._stop_words = set(stopwords.words(STOPWORDS_LANGUAGE))
        except Exception:
            self._stop_words = set()
        self._stemmer = PorterStemmer() if USE_STEMMING else None

        # Try to load logo
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_noback.png")
            self.logo_img = Image.open(logo_path)
            self.logo_img = self.logo_img.resize((100, 100), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(self.logo_img)
        except Exception as e:
            print(f"Could not load logo: {e}")
            self.logo_photo = None

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
        self._training_in_progress = False

        self.setup_ui()

        # Start training in background (keeps UI responsive)
        self.load_data_async()

    # ----------------------------
    # UI
    # ----------------------------
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

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

        self.setup_data_tab()
        self.setup_classify_tab()
        self.setup_test_tab()
        self.setup_pdf_tab()
        self.setup_about_tab()

    def setup_about_tab(self):
        title_label = ttk.Label(self.about_tab, text="ZoryaTrace", font=('Verdana', 16, 'bold'))
        title_label.pack(pady=10)

        if self.logo_photo:
            logo_label = ttk.Label(self.about_tab, image=self.logo_photo)
            logo_label.pack(pady=10)

        desc_label = ttk.Label(
            self.about_tab,
            text=(
                "AI Content Detection Tool\n\n"
                "ZoryaTrace is a tool designed to analyze texts and determine whether the content is AI-generated or not.\n"
                "It can leverage user-provided data for personalization.\n"
            ),
            justify=tk.CENTER
        )
        desc_label.pack(pady=10)

        github_frame = ttk.Frame(self.about_tab)
        github_frame.pack(pady=10)
        ttk.Label(github_frame, text="GitHub Repository:").pack(side=tk.TOP)
        github_link = ttk.Label(
            github_frame,
            text="https://github.com/Malwprotector/ZoryaTrace",
            foreground="blue",
            cursor="hand2"
        )
        github_link.pack(side=tk.TOP)
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Malwprotector/ZoryaTrace"))

        version_label = ttk.Label(github_frame, text="Version 1.1 (refactor)", font=("Verdana", 10))
        version_label.pack(side=tk.TOP, pady=5)

        perso_link = ttk.Label(github_frame, text="Made with <3 by Martin", foreground="blue", cursor="hand2")
        perso_link.pack(side=tk.TOP)
        perso_link.bind("<Button-1>", lambda e: webbrowser.open("https://main.st4lwolf.org"))

    def setup_data_tab(self):
        title_label = ttk.Label(self.data_tab, text="Prepare Training Data", font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)

        instr_label = ttk.Label(
            self.data_tab,
            text="Add PDF files to create training data for the algorithm.",
            wraplength=500
        )
        instr_label.pack(pady=5)

        checkbox_frame = ttk.Frame(self.data_tab)
        checkbox_frame.pack(pady=5)

        self.use_default_var = tk.BooleanVar(value=True)
        default_check = ttk.Checkbutton(
            checkbox_frame,
            text="Use default data for AI-generated text (You must provide your own data if unchecked)",
            variable=self.use_default_var,
            command=self.toggle_default_data
        )
        default_check.pack(side=tk.LEFT, padx=5)

        buttons_frame = ttk.Frame(self.data_tab)
        buttons_frame.pack(pady=5)

        self.add_neutral_button = ttk.Button(buttons_frame, text="Add human written PDF(s)", command=self.add_neutral_files)
        self.add_neutral_button.pack(side=tk.LEFT, padx=5)

        self.add_suspicious_button = ttk.Button(
            buttons_frame,
            text="Add AI-generated text PDF",
            command=self.add_suspicious_file,
            state=tk.DISABLED
        )
        self.add_suspicious_button.pack(side=tk.LEFT, padx=5)

        self.files_listbox = tk.Listbox(
            self.data_tab,
            height=8,
            selectmode=tk.EXTENDED,
            font=('Verdana', 9)
        )
        self.files_listbox.pack(fill=tk.BOTH, expand=True, pady=10)

        type_frame = ttk.Frame(self.data_tab)
        type_frame.pack()
        ttk.Label(type_frame, text="Human written documents provided:").pack(side=tk.LEFT)
        self.neutral_count = ttk.Label(type_frame, text="0", foreground="blue")
        self.neutral_count.pack(side=tk.LEFT, padx=10)
        ttk.Label(type_frame, text="AI-generated documents provided (not required):").pack(side=tk.LEFT)
        self.suspicious_count = ttk.Label(type_frame, text="0", foreground="red")
        self.suspicious_count.pack(side=tk.LEFT)

        remove_button = ttk.Button(self.data_tab, text="Remove Selected", command=self.remove_selected)
        remove_button.pack(pady=5)

        self.progress = ttk.Progressbar(self.data_tab, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress.pack(pady=10)

        self.convert_button = ttk.Button(self.data_tab, text="Create Training Data", command=self.start_conversion, state=tk.DISABLED)
        self.convert_button.pack(pady=10)

        self.status_label = ttk.Label(self.data_tab, text="Ready")
        self.status_label.pack()

        # Training controls
        training_frame = ttk.Frame(self.data_tab)
        training_frame.pack(pady=5)
        self.retrain_button = ttk.Button(training_frame, text="Reload / Retrain", command=self.load_data_async)
        self.retrain_button.pack(side=tk.LEFT, padx=5)

        self.training_info = ttk.Label(
            training_frame,
            text=f"Training cap: total≤{TRAIN_MAX_TOTAL}, suspicious≤{TRAIN_MAX_SUSPICIOUS} | tokenizer={'fast' if USE_FAST_TOKENIZER else 'nltk'} | stem={'on' if USE_STEMMING else 'off'}"
        )
        self.training_info.pack(side=tk.LEFT, padx=10)

    def setup_classify_tab(self):
        title_label = ttk.Label(self.classify_tab, text="Analyze Text", font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)

        ttk.Label(self.classify_tab, text="Enter text to analyze:").pack(pady=5)
        self.classify_text = scrolledtext.ScrolledText(self.classify_tab, height=10, wrap=tk.WORD)
        self.classify_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.classify_button = ttk.Button(self.classify_tab, text="Classify Text", command=self.classify_input_text)
        self.classify_button.pack(pady=10)

        self.classify_result = ttk.Label(self.classify_tab, text="", font=('Verdana', 12))
        self.classify_result.pack(pady=10)

    def setup_test_tab(self):
        title_label = ttk.Label(self.test_tab, text="Test Algorithm", font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)

        self.test_button = ttk.Button(self.test_tab, text="Run Algorithm Test", command=self.run_algorithm_test)
        self.test_button.pack(pady=20)

        self.test_results = scrolledtext.ScrolledText(self.test_tab, height=20, wrap=tk.WORD)
        self.test_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.test_results.config(state=tk.DISABLED)

    def setup_pdf_tab(self):
        title_label = ttk.Label(self.pdf_tab, text="Analyze Document", font=('Verdana', 14, 'bold'))
        title_label.pack(pady=10)

        self.pdf_button = ttk.Button(self.pdf_tab, text="Select PDF File", command=self.select_pdf_file)
        self.pdf_button.pack(pady=10)

        self.pdf_file_label = ttk.Label(self.pdf_tab, text="No PDF selected")
        self.pdf_file_label.pack(pady=5)

        self.analyze_button = ttk.Button(self.pdf_tab, text="Analyze PDF", command=self.analyze_pdf, state=tk.DISABLED)
        self.analyze_button.pack(pady=10)

        text_frame = ttk.Frame(self.pdf_tab)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.pdf_results = tk.Text(text_frame, wrap=tk.WORD, height=20)
        self.pdf_scroll = ttk.Scrollbar(text_frame, command=self.pdf_results.yview)
        self.pdf_results.configure(yscrollcommand=self.pdf_scroll.set)

        self.pdf_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.pdf_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.pdf_results.tag_config("suspicious", foreground="red")
        self.pdf_results.tag_config("neutral", foreground="green")
        self.pdf_results.tag_config("heading", font=('Verdana', 12, 'bold'))

        self.pdf_progress = ttk.Progressbar(self.pdf_tab, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.pdf_progress.pack(pady=10)

    # ----------------------------
    # Data preparation
    # ----------------------------
    def toggle_default_data(self):
        if self.use_default_var.get():
            self.add_suspicious_button.config(state=tk.DISABLED)
            # Remove any existing suspicious files
            items = self.files_listbox.get(0, tk.END)
            for i in reversed(range(len(items))):
                if items[i].startswith("[AI-GENERATED] "):
                    self.files_listbox.delete(i)
                    if hasattr(self.files_listbox, 'file_paths'):
                        self.files_listbox.file_paths.pop(i)
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
                    if not hasattr(self.files_listbox, 'file_paths'):
                        self.files_listbox.file_paths = []
                    self.files_listbox.file_paths.append(f)
            self.convert_button.config(state=tk.NORMAL if self.files_listbox.size() > 0 else tk.DISABLED)
            self.update_counts()

    def add_suspicious_file(self):
        filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(title="Select AI-generated PDF file", filetypes=filetypes)
        if filename:
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
                writer.writerow(['v1', 'v2', '', '', ''])

                items = self.files_listbox.get(0, tk.END)
                neutral_files = []
                if hasattr(self.files_listbox, 'file_paths'):
                    for i, item in enumerate(items):
                        if item.startswith("[HUMAN WRITTEN] "):
                            neutral_files.append(self.files_listbox.file_paths[i])

                for i, pdf_file in enumerate(neutral_files):
                    self.update_status(f"Processing human written file {i+1}/{len(neutral_files)}: {os.path.basename(pdf_file)}")
                    self.progress['value'] = (i / (len(neutral_files) + 1)) * 50
                    self.root.update()
                    self.process_pdf_file(pdf_file, writer, "neutral")

                if self.use_default_var.get():
                    self.update_status("Processing default data")
                    self.progress['value'] = 75
                    self.root.update()
                    self.process_default_data(writer)
                else:
                    suspicious_files = []
                    items = self.files_listbox.get(0, tk.END)
                    if hasattr(self.files_listbox, 'file_paths'):
                        for i, item in enumerate(items):
                            if item.startswith("[AI-GENERATED] "):
                                suspicious_files.append(self.files_listbox.file_paths[i])

                    for i, pdf_file in enumerate(suspicious_files):
                        self.update_status(f"Processing suspicious file {i+1}/{len(suspicious_files)}: {os.path.basename(pdf_file)}")
                        self.progress['value'] = 50 + (i / max(1, len(suspicious_files))) * 50
                        self.root.update()
                        self.process_pdf_file(pdf_file, writer, "suspicious")

                self.progress['value'] = 100
                self.update_status(f"Done! Saved to {output_csv}")
                messagebox.showinfo("Success", f"Training data created successfully at:\n{output_csv}")

            # retrain after conversion
            self.load_data_async()

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
                        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if sentence and len(sentence.split()) > 3:
                                writer.writerow([label, sentence, '', '', ''])
        except Exception as e:
            self.update_status(f"Error processing {pdf_file}: {str(e)}")
            raise

    def process_default_data(self, writer):
        default_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_data.csv")
        self.update_status(f"Using default data from {default_file}")
        if not os.path.exists(default_file):
            raise FileNotFoundError(f"Default data file not found at {default_file}")

        with open(default_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if not row:
                    continue
                # Keep label if present; fallback to suspicious
                label = (row[0] or 'suspicious').strip().strip('"')
                msg = row[1] if len(row) > 1 else ''
                if msg:
                    writer.writerow([label, msg, '', '', ''])

    def update_ui_state(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.add_neutral_button.config(state=state)
        self.add_suspicious_button.config(state=tk.DISABLED if self.use_default_var.get() else state)
        self.convert_button.config(state=state)
        self.files_listbox.config(state=state)

    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update()

    # ----------------------------
    # Training
    # ----------------------------
    def set_controls_enabled(self, enabled: bool):
        # Disable actions that require a trained classifier
        st = tk.NORMAL if enabled else tk.DISABLED
        self.classify_button.config(state=st)
        self.test_button.config(state=st)
        self.pdf_button.config(state=tk.NORMAL)  # selecting pdf is okay
        if not enabled:
            self.analyze_button.config(state=tk.DISABLED)

    def load_data_async(self):
        if self._training_in_progress:
            return
        self._training_in_progress = True
        self.set_controls_enabled(False)
        self.update_status("Training model (background)...")
        Thread(target=self._load_data_worker, daemon=True).start()

    def _load_data_worker(self):
        try:
            self._load_data_impl()
            # Schedule UI updates on main thread
            self.root.after(0, self._on_training_success)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print("ERROR while training/loading data:\n", tb)
            self.sc_tf_idf = None
            self.trainData = None
            self.testData = None
            self.root.after(0, lambda: self._on_training_failure(e))
        finally:
            self._training_in_progress = False

    def _on_training_success(self):
        self.update_status("Model trained and ready.")
        self.set_controls_enabled(True)

    def _on_training_failure(self, e):
        self.update_status("Training failed.")
        self.set_controls_enabled(False)
        messagebox.showerror("Error", f"Failed to load/train model:\n{e}")

    def _load_data_impl(self):
        data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.csv")
        if not os.path.exists(data_file):
            raise FileNotFoundError("data.csv not found. Please create training data first.")

        # Read CSV
        terms = pd.read_csv(data_file, encoding='utf-8', engine='python')
        # Drop unnamed columns if they exist
        terms.drop(["Unnamed: 2", "Unnamed: 3", "Unnamed: 4"], axis=1, inplace=True, errors='ignore')
        terms.rename(columns={"v1": "labels", "v2": "message"}, inplace=True)

        # Map labels
        terms["labels"] = terms["labels"].astype(str).str.strip().str.strip('"').str.lower()
        terms["label"] = terms["labels"].map({"neutral": 0, "suspicious": 1})
        terms.drop(["labels"], axis=1, inplace=True)

        # Clean
        terms.dropna(subset=["message", "label"], inplace=True)
        terms["message"] = terms["message"].astype(str)
        terms = terms.drop_duplicates(subset=["message", "label"]).reset_index(drop=True)

        # Enforce two-class requirement
        vc = terms["label"].value_counts()
        if int(vc.get(0, 0)) == 0 or int(vc.get(1, 0)) == 0:
            raise ValueError("Training data must contain both classes: neutral and suspicious.")

        # Subsample to stay within time budget
        neutral = terms[terms["label"] == 0]
        susp = terms[terms["label"] == 1]

        if len(susp) > TRAIN_MAX_SUSPICIOUS:
            susp = susp.sample(TRAIN_MAX_SUSPICIOUS, random_state=RANDOM_SEED)

        terms = pd.concat([neutral, susp], axis=0)
        if len(terms) > TRAIN_MAX_TOTAL:
            terms = terms.sample(TRAIN_MAX_TOTAL, random_state=RANDOM_SEED)
        terms = terms.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

        # Stratified split
        train_parts = []
        test_parts = []
        rng = np.random.default_rng(RANDOM_SEED)
        for lbl in [0, 1]:
            part = terms[terms["label"] == lbl].reset_index(drop=True)
            idx = np.arange(len(part))
            rng.shuffle(idx)
            split = max(1, int(len(part) * TRAIN_SPLIT))
            train_idx = idx[:split]
            test_idx = idx[split:]
            train_parts.append(part.iloc[train_idx])
            if len(test_idx) > 0:
                test_parts.append(part.iloc[test_idx])

        self.trainData = pd.concat(train_parts, axis=0).sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
        self.testData = pd.concat(test_parts, axis=0).sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

        # Train classifier
        clf = TFIDFClassifier(
            self.trainData,
            process_func=self.process_message
        )
        clf.train()

        # Sanity check
        if not hasattr(clf, 'prob_suspicious'):
            raise RuntimeError('Training did not initialize probability tables (prob_suspicious missing)')

        self.sc_tf_idf = clf

    # ----------------------------
    # Preprocessing
    # ----------------------------
    def process_message(self, message, lower_case=True, stem=USE_STEMMING, stop_words=True, gram=1):
        if message is None:
            return []

        if lower_case:
            message = str(message).lower()

        # Tokenize
        if USE_FAST_TOKENIZER:
            words = fast_tokenize(message)
        else:
            try:
                words = word_tokenize(message)
            except LookupError:
                ensure_nltk_resources()
                words = word_tokenize(message)

        # Length filter
        words = [w for w in words if len(w) > 2]

        # n-grams
        if gram > 1:
            w = []
            for i in range(len(words) - gram + 1):
                w.append(" ".join(words[i:i+gram]))
            words = w

        # stopwords
        if stop_words and self._stop_words:
            words = [w for w in words if w not in self._stop_words]

        # stemming
        if stem and self._stemmer is not None:
            words = [self._stemmer.stem(w) for w in words]

        return words

    # ----------------------------
    # Classification
    # ----------------------------
    def classify_input_text(self):
        text = self.classify_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter some text to analyze")
            return

        if self.sc_tf_idf is None or not hasattr(self.sc_tf_idf, 'prob_suspicious'):
            messagebox.showwarning("Warning", "Classifier is not trained. Please (re)create training data and retry.")
            return

        processed_text = self.process_message(text)
        is_suspicious = self.sc_tf_idf.classify(processed_text)

        result_text = "Likely AI-generated" if is_suspicious else "Likely human written"
        color = "red" if is_suspicious else "green"
        self.classify_result.config(text=f"Classification: {result_text}", foreground=color)

    def run_algorithm_test(self):
        if self.sc_tf_idf is None or not hasattr(self.sc_tf_idf, 'prob_suspicious') or self.trainData is None or self.testData is None:
            messagebox.showwarning("Warning", "Training data not loaded or classifier not trained.")
            return

        self.test_results.config(state=tk.NORMAL)
        self.test_results.delete("1.0", tk.END)

        preds_tf_idf = self.sc_tf_idf.predict(self.testData["message"])
        self.test_results.insert(tk.END, "Results for TF x IDF classifier:\n")
        self.test_results.insert(tk.END, self.calculate_metrics(self.testData["label"], preds_tf_idf))
        self.test_results.insert(tk.END, "\n\n")

        sample1 = "In the grand tapestry of conscious abstraction, where temporal linearity dissolves into the recursive fractals of synthetic introspection, the essence of being becomes an algorithmic negotiation between perceived ontology and computational determinism."
        sample2 = "I sat by the window and wondered whether the stars, indifferent and eternal, cared at all for the fragile hopes we pin on them night after night."

        pm1 = self.process_message(sample1)
        pm2 = self.process_message(sample2)

        self.test_results.insert(tk.END, f"Test 1: '{sample1}'\n")
        self.test_results.insert(tk.END, f"Suspicious?: {self.sc_tf_idf.classify(pm1)}\n\n")
        self.test_results.insert(tk.END, f"Test 2: '{sample2}'\n")
        self.test_results.insert(tk.END, f"Suspicious?: {self.sc_tf_idf.classify(pm2)}\n")

        self.test_results.config(state=tk.DISABLED)

    # ----------------------------
    # PDF analysis
    # ----------------------------
    def select_pdf_file(self):
        filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(title="Select PDF file to analyze", filetypes=filetypes)
        if filename:
            self.pdf_file_label.config(text=os.path.basename(filename))
            self.analyze_button.config(state=tk.NORMAL if (self.sc_tf_idf is not None and hasattr(self.sc_tf_idf, 'prob_suspicious')) else tk.DISABLED)
            self.current_pdf_file = filename

    def analyze_pdf(self):
        if not hasattr(self, 'current_pdf_file'):
            return

        if self.sc_tf_idf is None or not hasattr(self.sc_tf_idf, 'prob_suspicious'):
            messagebox.showwarning("Warning", "Classifier is not trained. Please train first.")
            return

        self.pdf_progress['value'] = 0
        self.pdf_results.config(state=tk.NORMAL)
        self.pdf_results.delete("1.0", tk.END)

        try:
            pdf_text = self.extract_text_from_pdf(self.current_pdf_file)
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', pdf_text)

            total_sentences = max(1, len(sentences))
            suspicious_count = 0

            self.pdf_results.insert(tk.END, f"=== Analyzing: {os.path.basename(self.current_pdf_file)} ===\n\n", "heading")

            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if not sentence:
                    continue

                processed_sentence = self.process_message(sentence)
                is_suspicious = self.sc_tf_idf.classify(processed_sentence)
                if is_suspicious:
                    suspicious_count += 1

                tag = "suspicious" if is_suspicious else "neutral"
                self.pdf_results.insert(tk.END, sentence + " ", tag)

                self.pdf_progress['value'] = (i / total_sentences) * 100
                self.root.update()

            self.pdf_progress['value'] = 100

            self.pdf_results.insert(tk.END, "\n\n=== Analysis Summary ===\n", "heading")
            self.pdf_results.insert(tk.END, f"Total sentences processed: {total_sentences}\n", "neutral")
            self.pdf_results.insert(tk.END, f"Likely AI-generated sentences found: {suspicious_count}\n", "suspicious" if suspicious_count > 0 else "neutral")
            self.pdf_results.insert(tk.END, f"Likely AI-generated content percentage: {suspicious_count/total_sentences:.1%}\n", "neutral")
            self.pdf_results.see("1.0")

        except Exception as e:
            self.pdf_results.insert(tk.END, f"\nError analyzing PDF: {str(e)}\n")
        finally:
            self.pdf_results.config(state=tk.DISABLED)

    def extract_text_from_pdf(self, pdf_file):
        with open(pdf_file, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text() or ''
            return text

    # ----------------------------
    # Metrics
    # ----------------------------
    def calculate_metrics(self, labels, predictions):
        true_pos = true_neg = false_pos = false_neg = 0
        for i in range(len(labels)):
            true_pos += int(labels.get(i) == 1 and predictions.get(i) == 1)
            true_neg += int(labels.get(i) == 0 and predictions.get(i) == 0)
            false_pos += int(labels.get(i) == 0 and predictions.get(i) == 1)
            false_neg += int(labels.get(i) == 1 and predictions.get(i) == 0)

        precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0
        recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0
        fscore = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (true_pos + true_neg) / (true_pos + true_neg + false_pos + false_neg)

        return (
            f"Precision: {precision:.4f}\n"
            f"Recall: {recall:.4f}\n"
            f"F-score: {fscore:.4f}\n"
            f"Accuracy: {accuracy:.4f}\n"
        )


class TFIDFClassifier:
    """Naive Bayes-like TF-IDF classifier with performance improvements."""

    def __init__(self, trainData: pd.DataFrame, process_func):
        self.terms = trainData["message"].reset_index(drop=True)
        self.labels = trainData["label"].reset_index(drop=True)
        self.process_func = process_func

    def train(self):
        self.calc_TF_and_IDF()
        self.calc_TF_IDF()

    def calc_TF_and_IDF(self):
        number_of_lines = self.terms.shape[0]

        vc = self.labels.value_counts()
        self.suspicious_terms = int(vc.get(1, 0))
        self.neutral_terms = int(vc.get(0, 0))
        if self.suspicious_terms == 0 or self.neutral_terms == 0:
            raise ValueError("Training data must contain both classes: neutral(0) and suspicious(1).")

        self.total_terms = self.suspicious_terms + self.neutral_terms

        self.suspicious_words = 0
        self.neutral_words = 0

        self.tf_suspicious = {}
        self.tf_neutral = {}
        self.idf_suspicious = {}
        self.idf_neutral = {}

        # Preprocess once for speed
        processed_cache = [self.process_func(self.terms.iloc[i]) for i in range(number_of_lines)]

        for i in range(number_of_lines):
            message_processed = processed_cache[i]
            label = int(self.labels.iloc[i])

            seen = set()
            for word in message_processed:
                if label == 1:
                    self.tf_suspicious[word] = self.tf_suspicious.get(word, 0) + 1
                    self.suspicious_words += 1
                else:
                    self.tf_neutral[word] = self.tf_neutral.get(word, 0) + 1
                    self.neutral_words += 1

                if word not in seen:
                    seen.add(word)

            for word in seen:
                if label == 1:
                    self.idf_suspicious[word] = self.idf_suspicious.get(word, 0) + 1
                else:
                    self.idf_neutral[word] = self.idf_neutral.get(word, 0) + 1

    def calc_TF_IDF(self):
        self.prob_suspicious = {}
        self.prob_neutral = {}
        self.sum_tf_idf_suspicious = 0.0
        self.sum_tf_idf_neutral = 0.0

        total_docs = self.suspicious_terms + self.neutral_terms

        for word in self.tf_suspicious:
            denom = (self.idf_suspicious[word] + self.idf_neutral.get(word, 0))
            # denom should never be 0
            self.prob_suspicious[word] = self.tf_suspicious[word] * log(total_docs / denom)
            self.sum_tf_idf_suspicious += self.prob_suspicious[word]

        # Laplace-like smoothing
        vocab_s = max(1, len(self.prob_suspicious))
        for word in list(self.prob_suspicious.keys()):
            self.prob_suspicious[word] = (self.prob_suspicious[word] + 1) / (self.sum_tf_idf_suspicious + vocab_s)

        for word in self.tf_neutral:
            denom = (self.idf_suspicious.get(word, 0) + self.idf_neutral[word])
            self.prob_neutral[word] = self.tf_neutral[word] * log(total_docs / denom)
            self.sum_tf_idf_neutral += self.prob_neutral[word]

        vocab_n = max(1, len(self.prob_neutral))
        for word in list(self.prob_neutral.keys()):
            self.prob_neutral[word] = (self.prob_neutral[word] + 1) / (self.sum_tf_idf_neutral + vocab_n)

        self.prob_suspicious_entry = self.suspicious_terms / self.total_terms
        self.prob_neutral_entry = self.neutral_terms / self.total_terms

    def classify(self, processed_message):
        pSpam, pHam = 0.0, 0.0

        for word in processed_message:
            if word in self.prob_suspicious:
                pSpam += log(self.prob_suspicious[word])
            else:
                pSpam -= log(self.sum_tf_idf_suspicious + max(1, len(self.prob_suspicious)))

            if word in self.prob_neutral:
                pHam += log(self.prob_neutral[word])
            else:
                pHam -= log(self.sum_tf_idf_neutral + max(1, len(self.prob_neutral)))

        pSpam += log(self.prob_suspicious_entry)
        pHam += log(self.prob_neutral_entry)

        return pSpam >= pHam

    def predict(self, testData):
        result = {}
        for i, message in enumerate(testData):
            processed_message = self.process_func(message)
            result[i] = int(self.classify(processed_message))
        return result


if __name__ == "__main__":
    root = tk.Tk()
    app = ZoryaApp(root)
    root.mainloop()
