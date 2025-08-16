import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from tkinter import font as tkfont
import os
import queue
import threading
import time
from audio_text_extractor import ArabicAudioTranscriber

class TranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arabic Audio/Video Transcriber")
        self.root.geometry("800x600")
        self.setup_ui()
        self.files_to_process = []
        self.stop_flag = False
        self.processing = False
        self.log_queue = queue.Queue()
        self.update_log()
        
    def setup_ui(self):
        # Configure styles
        style = ttk.Style()
        style.configure('TButton', padding=5)
        style.configure('TFrame', padding=5)
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Files to Transcribe", padding=5)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.file_listbox = tk.Listbox(file_frame, height=5)
        self.file_listbox.pack(fill=tk.X, expand=True, pady=5)
        
        btn_frame = ttk.Frame(file_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_files).pack(side=tk.LEFT, padx=2)
        
        # Model selection
        model_frame = ttk.LabelFrame(main_frame, text="Model Settings", padding=5)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="Model:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar(value="base")
        models = ["base", "small", "medium", "large-v2", "large-v3"]
        self.model_menu = ttk.Combobox(model_frame, textvariable=self.model_var, values=models, state="readonly")
        self.model_menu.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Progress
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding=5)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, expand=True, pady=5)
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.start_btn = ttk.Button(control_frame, text="Start Transcription", command=self.start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=2)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)
        
        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def log(self, message):
        self.log_queue.put(f"{time.strftime('%H:%M:%S')} - {message}")
        
    def update_log(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                self.root.update_idletasks()
        except queue.Empty:
            pass
        self.root.after(100, self.update_log)
        
    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Select Audio/Video Files",
            filetypes=[
                ("Media files", "*.mp3 *.wav *.ogg *.m4a *.mp4 *.avi *.mkv *.mov"),
                ("Audio files", "*.mp3 *.wav *.ogg *.m4a"),
                ("Video files", "*.mp4 *.avi *.mkv *.mov"),
                ("All files", "*.*")
            ]
        )
        for file in files:
            if file not in self.files_to_process:
                self.files_to_process.append(file)
                self.file_listbox.insert(tk.END, os.path.basename(file))
                
    def remove_selected(self):
        selected = self.file_listbox.curselection()
        for i in selected[::-1]:
            self.files_to_process.pop(i)
            self.file_listbox.delete(i)
            
    def clear_files(self):
        self.files_to_process.clear()
        self.file_listbox.delete(0, tk.END)
        
    def on_closing(self):
        if self.processing:
            if messagebox.askokcancel("Quit", "Transcription is in progress. This will stop the current process. Are you sure you want to quit?"):
                self.stop_flag = True
                self.processing = False
                if hasattr(self, 'transcriber') and hasattr(self.transcriber, 'stop_transcription'):
                    self.transcriber.stop_transcription()
                self.root.destroy()
        else:
            self.root.destroy()
            
    def start_processing(self):
        if not self.files_to_process:
            messagebox.showwarning("Warning", "Please add files to transcribe first.")
            return
            
        self.processing = True
        self.stop_flag = False
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Start processing in a separate thread
        self.worker_thread = threading.Thread(target=self.process_files)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
    def stop_processing(self):
        if self.processing:
            self.stop_flag = True
            self.processing = False
            # Force stop any ongoing transcription
            if hasattr(self, 'transcriber') and hasattr(self.transcriber, 'stop_transcription'):
                self.transcriber.stop_transcription()
            self.log("Stopped transcription process")
            
    def process_files(self):
        model_name = self.model_var.get()
        total_files = len(self.files_to_process)
        self.transcriber = ArabicAudioTranscriber(model_name=model_name)
        
        for i, file_path in enumerate(self.files_to_process, 1):
            if self.stop_flag or not self.processing:
                break
                
            self.log(f"Processing file {i} of {total_files}: {os.path.basename(file_path)}")
            self.progress_var.set((i-1) / total_files * 100)
            self.root.update_idletasks()
            
            try:
                # Generate output path (same name with .txt extension)
                output_path = os.path.splitext(file_path)[0] + ".txt"
                
                # Transcribe
                self.transcriber.transcribe_media(
                    media_path=file_path,
                    output_path=output_path
                )
                
                self.log(f"Successfully transcribed: {os.path.basename(file_path)}")
                
            except Exception as e:
                self.log(f"Error processing {os.path.basename(file_path)}: {str(e)}")
                
            # Update progress
            self.progress_var.set(i / total_files * 100)
            self.root.update_idletasks()
        
        # Clean up
        self.processing = False
        self.root.after(0, self.processing_finished)
        
    def processing_finished(self):
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.log("Processing completed!")
        
        if not self.stop_flag:
            messagebox.showinfo("Success", "All files have been processed successfully!")
        else:
            messagebox.showinfo("Stopped", "Processing was stopped by user.")

def main():
    root = tk.Tk()
    app = TranscriberApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
