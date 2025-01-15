import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import json
from pathlib import Path

class AWSExamValidatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AWS Exam Validator")
        self.root.geometry("800x600")
        
        self.validator = None
        self.questions = {}
        self.current_question = 1
        self.student_answers = {}
        
        self.setup_gui()
        
    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # File selection buttons
        ttk.Button(main_frame, text="Select Solutions File", 
                  command=self.load_solutions).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(main_frame, text="Select Questions File", 
                  command=self.load_questions).grid(row=0, column=1, padx=5, pady=5)
        
        # Question display
        self.question_frame = ttk.LabelFrame(main_frame, text="Question", padding="10")
        self.question_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.question_text = tk.Text(self.question_frame, height=8, width=80, wrap=tk.WORD)
        self.question_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.selected_option = tk.StringVar()
        self.option_buttons = []
        for i, opt in enumerate(['A', 'B', 'C', 'D', 'E']):
            rb = ttk.Radiobutton(options_frame, text="", variable=self.selected_option, 
                               value=opt, command=self.save_answer)
            rb.grid(row=i, column=0, sticky=tk.W)
            self.option_buttons.append(rb)
            
        # Navigation frame
        nav_frame = ttk.Frame(main_frame)
        nav_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(nav_frame, text="Previous", command=self.prev_question).grid(row=0, column=0, padx=5)
        ttk.Button(nav_frame, text="Next", command=self.next_question).grid(row=0, column=1, padx=5)
        ttk.Button(nav_frame, text="Submit", command=self.submit_exam).grid(row=0, column=2, padx=5)
        
        # Progress
        self.progress_var = tk.StringVar(value="Question 0/0")
        ttk.Label(nav_frame, textvariable=self.progress_var).grid(row=0, column=3, padx=20)

    def load_solutions(self):
        filename = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if filename:
            try:
                self.validator = AWSExamValidator(filename)
                messagebox.showinfo("Success", "Solutions file loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Error loading solutions file: {str(e)}")

    def load_questions(self):
        if not self.validator:
            messagebox.showwarning("Warning", "Please load solutions file first!")
            return
            
        filename = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if filename:
            try:
                self.questions = self.validator.read_text_questions(filename)
                self.current_question = 1
                self.student_answers = {}
                self.display_question()
                messagebox.showinfo("Success", "Questions loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Error loading questions: {str(e)}")

    def display_question(self):
        if not self.questions:
            return
            
        question_data = self.questions.get(self.current_question)
        if not question_data:
            return
            
        self.question_text.delete('1.0', tk.END)
        self.question_text.insert('1.0', question_data['question'])
        
        for i, (opt, text) in enumerate(question_data['options'].items()):
            self.option_buttons[i].config(text=f"{opt}. {text}")
            
        self.selected_option.set(self.student_answers.get(self.current_question, ''))
        self.progress_var.set(f"Question {self.current_question}/{len(self.questions)}")

    def save_answer(self):
        if self.current_question in self.questions:
            self.student_answers[self.current_question] = self.selected_option.get()

    def next_question(self):
        if self.current_question < len(self.questions):
            self.current_question += 1
            self.display_question()

    def prev_question(self):
        if self.current_question > 1:
            self.current_question -= 1
            self.display_question()

    def submit_exam(self):
        if not self.student_answers:
            messagebox.showwarning("Warning", "No answers to submit!")
            return
            
        results = self.validator.validate_answers(self.student_answers)
        
        results_window = tk.Toplevel(self.root)
        results_window.title("Exam Results")
        results_window.geometry("600x400")
        
        results_text = tk.Text(results_window, height=20, width=70)
        results_text.pack(padx=10, pady=10)
        
        results_text.insert('1.0', f"Exam Results:\n\n")
        results_text.insert('end', f"Total Questions: {results['total_questions']}\n")
        results_text.insert('end', f"Correct Answers: {results['correct_answers']}\n")
        results_text.insert('end', f"Score: {results['score_percentage']:.2f}%\n\n")
        
        if results['incorrect_answers']:
            results_text.insert('end', "Incorrect Answers:\n")
            for wrong in results['incorrect_answers']:
                results_text.insert('end', 
                    f"Question {wrong['question']}: You answered {wrong['student_answer']}, "
                    f"correct answer was {wrong['correct_answer']}\n")
        
        results_text.config(state='disabled')

class AWSExamValidator:
    def __init__(self, solutions_file):
        self.solutions = self._parse_solutions(solutions_file)
        
    def _parse_solutions(self, solutions_file):
        solutions = {}
        
        with open(solutions_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        questions = content.split('\n\n')
        
        for question in questions:
            match = re.match(r'(\d+)]', question)
            if match:
                question_num = int(match.group(1))
                ans_match = re.search(r'ans[-\s]*([A-E])', question, re.IGNORECASE)
                if ans_match:
                    solutions[question_num] = ans_match.group(1).upper()
                    
        return solutions

    def read_text_questions(self, text_file):
        questions = {}
        
        with open(text_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Adjusted regex pattern to handle errors
        question_pattern = r'(\d+)[\.)]\s+(.*?)\s+(?:A[\.)]|A\s+)(.*?)\s+(?:B[\.)]|B\s+)(.*?)\s+(?:C[\.)]|C\s+)(.*?)\s+(?:D[\.)]|D\s+)(.*?)(?=\n\d+[\.)]|$)'
        try:
            matches = re.finditer(question_pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                question_num = int(match.group(1))
                questions[question_num] = {
                    'question': match.group(2).strip(),
                    'options': {
                        'A': match.group(3).strip(),
                        'B': match.group(4).strip(),
                        'C': match.group(5).strip(),
                        'D': match.group(6).strip()
                    }
                }
        except re.error as e:
            raise ValueError(f"Regex error: {e}")
        
        return questions

    def validate_answers(self, student_answers):
        results = {
            'total_questions': len(self.solutions),
            'correct_answers': 0,
            'incorrect_answers': [],
            'score_percentage': 0
        }
        
        for question_num, student_answer in student_answers.items():
            if question_num in self.solutions:
                if student_answer.upper() == self.solutions[question_num]:
                    results['correct_answers'] += 1
                else:
                    results['incorrect_answers'].append({
                        'question': question_num,
                        'student_answer': student_answer,
                        'correct_answer': self.solutions[question_num]
                    })
                    
        results['score_percentage'] = (results['correct_answers'] / results['total_questions']) * 100
        return results

def main():
    root = tk.Tk()
    app = AWSExamValidatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
