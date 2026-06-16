#!/usr/bin/env python3
# =============================================================================
# File:         call_report_gui.py
# Version:      1.2.0
# Date:         2026-02-28
# Description:  GUI for generating call reports with flexible date/time
# Update:       Fixed no data handling and status mapping
# Location:     D:\Altria_Ops\gui\call_report_gui.py
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
import csv
import json

class CallReportGUI:
    def __init__(self, master):
        self.master = master
        master.title("Call Center Report Generator")
        master.geometry("1200x800")
        master.minsize(1000, 700)
        
        # Set style
        self.style = ttk.Style()
        self.style.configure("Header.TLabel", font=('Arial', 14, 'bold'))
        self.style.configure("SubHeader.TLabel", font=('Arial', 12, 'bold'))
        self.style.configure("Success.TLabel", foreground="green")
        self.style.configure("Error.TLabel", foreground="red")
        
        # Variables
        self.start_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.start_time_var = tk.StringVar(value="00:00")
        self.end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.end_time_var = tk.StringVar(value="23:59")
        self.campaign_var = tk.StringVar(value="ALL")
        self.report_type_var = tk.StringVar(value="api")
        self.status_filter_var = tk.StringVar(value="ALL")
        
        # Data storage
        self.report_data = None
        self.campaigns = []
        
        self.setup_ui()
        self.load_campaigns()
        
    def setup_ui(self):
        """Setup the main UI"""
        # Main container
        main = ttk.Frame(self.master, padding="10")
        main.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(main, text="CALL CENTER REPORT GENERATOR", 
                           style="Header.TLabel")
        header.pack(pady=10)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Report Generation Tab
        self.setup_report_tab(notebook)
        
        # Results Tab
        self.setup_results_tab(notebook)
        
        # Export Tab
        self.setup_export_tab(notebook)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main, textvariable=self.status_var, 
                               relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=5)
        
    def setup_report_tab(self, notebook):
        """Setup the report generation tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Generate Report")
        
        # Left frame for controls
        control_frame = ttk.LabelFrame(tab, text="Report Controls", padding="10")
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Date/Time Selection
        dt_frame = ttk.LabelFrame(control_frame, text="Date & Time Range", padding="10")
        dt_frame.pack(fill=tk.X, pady=5)
        
        # Start Date
        ttk.Label(dt_frame, text="Start Date:").grid(row=0, column=0, sticky=tk.W, pady=2)
        start_date_entry = ttk.Entry(dt_frame, textvariable=self.start_date_var, width=12)
        start_date_entry.grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(dt_frame, text="📅", width=3, 
                  command=lambda: self.pick_date(self.start_date_var)).grid(row=0, column=2)
        
        # Start Time
        ttk.Label(dt_frame, text="Start Time:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(dt_frame, textvariable=self.start_time_var, width=12).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(dt_frame, text="(HH:MM)").grid(row=1, column=2, sticky=tk.W)
        
        # End Date
        ttk.Label(dt_frame, text="End Date:").grid(row=2, column=0, sticky=tk.W, pady=2)
        end_date_entry = ttk.Entry(dt_frame, textvariable=self.end_date_var, width=12)
        end_date_entry.grid(row=2, column=1, padx=5, pady=2)
        ttk.Button(dt_frame, text="📅", width=3,
                  command=lambda: self.pick_date(self.end_date_var)).grid(row=2, column=2)
        
        # End Time
        ttk.Label(dt_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(dt_frame, textvariable=self.end_time_var, width=12).grid(row=3, column=1, padx=5, pady=2)
        ttk.Label(dt_frame, text="(HH:MM)").grid(row=3, column=2, sticky=tk.W)
        
        # Quick Select Buttons
        quick_frame = ttk.LabelFrame(control_frame, text="Quick Select", padding="10")
        quick_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(quick_frame, text="Today", 
                  command=self.set_today).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Yesterday", 
                  command=self.set_yesterday).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="This Week", 
                  command=self.set_this_week).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Last 7 Days", 
                  command=self.set_last_7_days).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Last 30 Days", 
                  command=self.set_last_30_days).pack(fill=tk.X, pady=2)
        
        # Campaign Selection
        camp_frame = ttk.LabelFrame(control_frame, text="Campaign Selection", padding="10")
        camp_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(camp_frame, text="All Campaigns", 
                       variable=self.campaign_var, value="ALL").pack(anchor=tk.W)
        ttk.Radiobutton(camp_frame, text="Specific Campaign", 
                       variable=self.campaign_var, value="SPECIFIC").pack(anchor=tk.W)
        
        self.campaign_combo = ttk.Combobox(camp_frame, state="readonly", width=30)
        self.campaign_combo.pack(fill=tk.X, pady=5)
        self.campaign_combo.bind('<<ComboboxSelected>>', 
                                 lambda e: self.campaign_var.set("SPECIFIC"))
        
        # Report Type
        type_frame = ttk.LabelFrame(control_frame, text="Report Type", padding="10")
        type_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(type_frame, text="API Format (Status-based)",
                       variable=self.report_type_var, value="api").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Detailed Format (All calls)",
                       variable=self.report_type_var, value="detailed").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Agent Performance",
                       variable=self.report_type_var, value="agent").pack(anchor=tk.W)
        
        # Status Filter (for API format)
        status_frame = ttk.LabelFrame(control_frame, text="Status Filter", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(status_frame, text="All Statuses",
                       variable=self.status_filter_var, value="ALL").pack(anchor=tk.W)
        ttk.Radiobutton(status_frame, text="Answered Only",
                       variable=self.status_filter_var, value="ANSWERED").pack(anchor=tk.W)
        ttk.Radiobutton(status_frame, text="Unanswered Only",
                       variable=self.status_filter_var, value="UNANSWERED").pack(anchor=tk.W)
        
        # Generate Button
        generate_btn = ttk.Button(control_frame, text="📊 GENERATE REPORT",
                                  command=self.generate_report)
        generate_btn.pack(fill=tk.X, pady=20)
        
        # Right frame for preview
        preview_frame = ttk.LabelFrame(tab, text="Report Preview", padding="10")
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Preview text widget with scrollbar
        text_frame = ttk.Frame(preview_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.preview_text = tk.Text(text_frame, wrap=tk.NONE, font=('Courier', 10))
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        v_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, 
                                     command=self.preview_text.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.config(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.HORIZONTAL,
                                     command=self.preview_text.xview)
        h_scrollbar.pack(fill=tk.X)
        self.preview_text.config(xscrollcommand=h_scrollbar.set)
        
    def setup_results_tab(self, notebook):
        """Setup the results tab with treeview"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Detailed Results")
        
        # Create treeview with scrollbars
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview
        self.result_tree = ttk.Treeview(tree_frame, show="tree headings")
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=self.result_tree.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_tree.config(yscrollcommand=v_scroll.set)
        
        h_scroll = ttk.Scrollbar(tab, orient=tk.HORIZONTAL,
                                  command=self.result_tree.xview)
        h_scroll.pack(fill=tk.X)
        self.result_tree.config(xscrollcommand=h_scroll.set)
        
    def setup_export_tab(self, notebook):
        """Setup the export tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Export")
        
        # Export options
        options_frame = ttk.LabelFrame(tab, text="Export Options", padding="20")
        options_frame.pack(pady=50)
        
        ttk.Button(options_frame, text="📄 Export to CSV",
                  command=self.export_csv,
                  width=30).pack(pady=5)
        
        ttk.Button(options_frame, text="📑 Export to JSON",
                  command=self.export_json,
                  width=30).pack(pady=5)
        
        ttk.Button(options_frame, text="📋 Copy to Clipboard",
                  command=self.copy_to_clipboard,
                  width=30).pack(pady=5)
        
        ttk.Button(options_frame, text="🖨️ Print Report",
                  command=self.print_report,
                  width=30).pack(pady=5)
        
    def load_campaigns(self):
        """Load list of campaigns"""
        try:
            query = """
            SELECT DISTINCT campaign_id
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY campaign_id
            """
            results = db.execute_query(query)
            self.campaigns = [r['campaign_id'] for r in results] if results else []
            self.campaign_combo['values'] = self.campaigns
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load campaigns: {e}")
            
    def pick_date(self, var):
        """Open date picker dialog"""
        # Simple date input dialog
        dialog = tk.Toplevel(self.master)
        dialog.title("Select Date")
        dialog.geometry("300x200")
        dialog.transient(self.master)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter date (YYYY-MM-DD):").pack(pady=20)
        
        date_entry = ttk.Entry(dialog)
        date_entry.pack(pady=10)
        date_entry.insert(0, var.get())
        
        def set_date():
            new_date = date_entry.get().strip()
            try:
                datetime.strptime(new_date, '%Y-%m-%d')
                var.set(new_date)
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
        
        ttk.Button(dialog, text="OK", command=set_date).pack(pady=10)
        
    def set_today(self):
        """Set date range to today"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.start_date_var.set(today)
        self.end_date_var.set(today)
        self.start_time_var.set("00:00")
        self.end_time_var.set("23:59")
        
    def set_yesterday(self):
        """Set date range to yesterday"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.start_date_var.set(yesterday)
        self.end_date_var.set(yesterday)
        self.start_time_var.set("00:00")
        self.end_time_var.set("23:59")
        
    def set_this_week(self):
        """Set date range to this week (Mon-Sun)"""
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        self.start_date_var.set(start.strftime("%Y-%m-%d"))
        self.end_date_var.set(end.strftime("%Y-%m-%d"))
        self.start_time_var.set("00:00")
        self.end_time_var.set("23:59")
        
    def set_last_7_days(self):
        """Set date range to last 7 days"""
        end = datetime.now()
        start = end - timedelta(days=6)
        self.start_date_var.set(start.strftime("%Y-%m-%d"))
        self.end_date_var.set(end.strftime("%Y-%m-%d"))
        self.start_time_var.set("00:00")
        self.end_time_var.set("23:59")
        
    def set_last_30_days(self):
        """Set date range to last 30 days"""
        end = datetime.now()
        start = end - timedelta(days=29)
        self.start_date_var.set(start.strftime("%Y-%m-%d"))
        self.end_date_var.set(end.strftime("%Y-%m-%d"))
        self.start_time_var.set("00:00")
        self.end_time_var.set("23:59")
        
    def generate_report(self):
        """Generate the report based on selected options"""
        self.status_var.set("Generating report...")
        self.master.update()
        
        try:
            # Parse dates and times
            start_date = datetime.strptime(self.start_date_var.get(), "%Y-%m-%d").date()
            end_date = datetime.strptime(self.end_date_var.get(), "%Y-%m-%d").date()
            
            start_time = self.start_time_var.get().strip()
            if ':' not in start_time:
                start_time += ":00"
            end_time = self.end_time_var.get().strip()
            if ':' not in end_time:
                end_time += ":00"
            
            start_dt = datetime.combine(start_date, datetime.strptime(start_time, "%H:%M").time())
            end_dt = datetime.combine(end_date, datetime.strptime(end_time, "%H:%M").time())
            
            # Get campaign filter
            campaign = None
            if self.campaign_var.get() == "SPECIFIC":
                campaign = self.campaign_combo.get()
                
            # Generate based on report type
            if self.report_type_var.get() == "api":
                report = self.generate_api_report(start_dt, end_dt, campaign)
            elif self.report_type_var.get() == "detailed":
                report = self.generate_detailed_report(start_dt, end_dt, campaign)
            else:
                report = self.generate_agent_report(start_dt, end_dt, campaign)
                
            # Display preview
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, report)
            
            # Update status based on content
            if "No data found" in report:
                self.status_var.set("No data found for selected period")
            else:
                lines = len(report.split('\n'))
                self.status_var.set(f"Report generated successfully! ({lines} lines)")
            
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to generate report: {e}")
            
    def generate_api_report(self, start_dt, end_dt, campaign):
        """Generate API-style report with updated status mapping"""
        params = [start_dt, end_dt]
        campaign_filter = ""
        
        if campaign:
            campaign_filter = "AND c.campaign_id = %s"
            params.append(campaign)
            
        report = []
        report.append("=" * 80)
        report.append(f"CALL SUMMARY REPORT".center(80))
        report.append("=" * 80)
        report.append(f"Period: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}")
        if campaign:
            report.append(f"Campaign: {campaign}")
        report.append("")
        
        # Summary
        summary_query = f"""
        SELECT 
            COUNT(*) as total_calls,
            SUM(CASE WHEN c.term_reason IN ('INCALL', 'ANSWER', 'COMPLETE', 'HANDLED', 'AGENT') 
                     THEN 1 ELSE 0 END) as total_handled
        FROM vicidial_closer_log c
        WHERE c.call_date BETWEEN %s AND %s
        {campaign_filter}
        """
        
        summary = db.execute_query(summary_query, params)
        
        if not summary or summary[0]['total_calls'] == 0:
            return "📊 No data found for the selected period.\n\nTry adjusting your date range or campaign selection."
            
        total = summary[0]['total_calls']
        handled = summary[0]['total_handled'] or 0
        unanswered = total - handled
        
        report.append("📊 CALL SUMMARY")
        report.append("-" * 40)
        report.append(f"{'Metric':<30} {'Count':>10}")
        report.append("-" * 40)
        report.append(f"{'Total Calls':<30} {total:>10}")
        report.append(f"{'Total Handled by Agents':<30} {handled:>10}")
        report.append(f"{'Total Unanswered/Dropped':<30} {unanswered:>10}")
        
        # Status breakdown with updated mapping
        status_query = f"""
        SELECT 
            c.term_reason as status,
            COUNT(*) as count,
            CASE 
                -- Answered calls
                WHEN c.term_reason IN ('INCALL', 'ANSWER', 'COMPLETE', 'HANDLED', 'AGENT') THEN 'Answered'
                
                -- Dropped/Abandoned
                WHEN c.term_reason IN ('DROP', 'ABANDON', 'QUEUETIMEOUT', 'NOAGENT', 'CALLER') THEN 'Dropped'
                
                -- After Hours
                WHEN c.term_reason IN ('AFTHRS', 'AFTERHOURS') THEN 'After Hours'
                
                -- Refund related
                WHEN c.term_reason = 'REFREQ' THEN 'Full Refund'
                WHEN c.term_reason = 'PRFND' THEN 'Partial Refund'
                WHEN c.term_reason = 'REFSTS' THEN 'Refund Status'
                
                -- Inquiry
                WHEN c.term_reason = 'PDINQY' THEN 'Product Inquiry'
                
                -- Queue
                WHEN c.term_reason = 'QUEUE' THEN 'In Queue'
                
                -- Ghost/Invalid
                WHEN c.term_reason = 'GC' THEN 'Ghost Call'
                
                -- Department
                WHEN c.term_reason = 'WDEPT' THEN 'Wrong Department'
                
                -- Cancellation
                WHEN c.term_reason = 'CANCEL' THEN 'Cancellation'
                
                -- No status
                WHEN c.term_reason = 'NONE' THEN 'No Status'
                
                -- Everything else
                ELSE 'Other'
            END as description
        FROM vicidial_closer_log c
        WHERE c.call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY c.term_reason
        ORDER BY count DESC
        """
        
        status_results = db.execute_query(status_query, params)
        
        if status_results:
            report.append("")
            report.append("=" * 80)
            report.append("BY STATUS TYPE".center(80))
            report.append("=" * 80)
            report.append(f"{'Status':<10} {'Count':<8} {'Description'}")
            report.append("-" * 80)
            
            for s in status_results:
                report.append(f"{s['status']:<10} {s['count']:<8} {s['description']}")
                
        # Agent breakdown
        agent_query = f"""
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as calls_handled
        FROM vicidial_agent_log a
        JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE c.call_date BETWEEN %s AND %s
          AND c.term_reason IN ('INCALL', 'ANSWER', 'COMPLETE', 'HANDLED', 'AGENT')
        {campaign_filter.replace('c.', 'c.') if campaign_filter else ''}
        GROUP BY a.user, u.full_name
        ORDER BY calls_handled DESC
        """
        
        agent_results = db.execute_query(agent_query, params)
        
        if agent_results:
            report.append("")
            report.append("=" * 80)
            report.append("BY AGENT".center(80))
            report.append("=" * 80)
            report.append(f"{'Agent':<15} {'Full Name':<25} {'Calls Handled':<15}")
            report.append("-" * 80)
            
            total_agent_calls = 0
            for a in agent_results:
                name = a['full_name'] or a['user']
                report.append(f"{a['user']:<15} {name:<25} {a['calls_handled']:<15}")
                total_agent_calls += a['calls_handled']
            
            if total_agent_calls > 0:
                report.append("-" * 80)
                report.append(f"{'TOTAL':<42} {total_agent_calls}")
            
        # Hourly breakdown
        hourly_query = f"""
        SELECT 
            HOUR(c.call_date) as hour,
            COUNT(*) as calls
        FROM vicidial_closer_log c
        WHERE c.call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY HOUR(c.call_date)
        ORDER BY hour
        """
        
        hourly_results = db.execute_query(hourly_query, params)
        
        if hourly_results:
            report.append("")
            report.append("=" * 80)
            report.append("CALL VOLUME BY HOUR".center(80))
            report.append("=" * 80)
            report.append(f"{'Hour':<15} {'Calls'}")
            report.append("-" * 80)
            
            for h in hourly_results:
                hour = h['hour']
                next_hour = (hour + 1) % 24
                report.append(f"{hour:02d}:00-{next_hour:02d}:00  {h['calls']}")
        
        # Add a small note about the data
        report.append("")
        report.append("-" * 80)
        report.append(f"✅ Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        return "\n".join(report)
        
    def generate_detailed_report(self, start_dt, end_dt, campaign):
        """Generate detailed report with all calls"""
        # Check if there's data first
        check_query = f"""
        SELECT COUNT(*) as count
        FROM vicidial_closer_log c
        WHERE c.call_date BETWEEN %s AND %s
        """
        params = [start_dt, end_dt]
        if campaign:
            check_query += " AND c.campaign_id = %s"
            params.append(campaign)
            
        result = db.execute_query(check_query, params)
        
        if not result or result[0]['count'] == 0:
            return "📊 No data found for the selected period.\n\nTry adjusting your date range or campaign selection."
            
        report = []
        report.append("=" * 80)
        report.append("DETAILED REPORT".center(80))
        report.append("=" * 80)
        report.append(f"Period: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}")
        if campaign:
            report.append(f"Campaign: {campaign}")
        report.append("")
        report.append("This feature is under development and will include:")
        report.append("  • Individual call details")
        report.append("  • Agent performance metrics")
        report.append("  • Campaign comparisons")
        report.append("  • Export capabilities")
        report.append("")
        report.append("-" * 80)
        report.append(f"✅ Preview generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        return "\n".join(report)
        
    def generate_agent_report(self, start_dt, end_dt, campaign):
        """Generate agent performance report"""
        # Check if there's data first
        check_query = f"""
        SELECT COUNT(*) as count
        FROM vicidial_agent_log a
        JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
        WHERE c.call_date BETWEEN %s AND %s
        """
        params = [start_dt, end_dt]
        if campaign:
            check_query += " AND c.campaign_id = %s"
            params.append(campaign)
            
        result = db.execute_query(check_query, params)
        
        if not result or result[0]['count'] == 0:
            return "📊 No agent activity found for the selected period.\n\nTry adjusting your date range or campaign selection."
            
        report = []
        report.append("=" * 80)
        report.append("AGENT PERFORMANCE REPORT".center(80))
        report.append("=" * 80)
        report.append(f"Period: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}")
        if campaign:
            report.append(f"Campaign: {campaign}")
        report.append("")
        report.append("This feature is under development and will include:")
        report.append("  • Agent call volumes")
        report.append("  • Average handle times")
        report.append("  • Performance rankings")
        report.append("  • Quality metrics")
        report.append("")
        report.append("-" * 80)
        report.append(f"✅ Preview generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        return "\n".join(report)
        
    def export_csv(self):
        """Export report to CSV"""
        if not self.preview_text.get(1.0, tk.END).strip():
            messagebox.showwarning("No Data", "Generate a report first")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"call_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    f.write(self.preview_text.get(1.0, tk.END))
                messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                self.status_var.set(f"Exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
                
    def export_json(self):
        """Export report to JSON"""
        messagebox.showinfo("Info", "JSON export - Coming soon!")
        
    def copy_to_clipboard(self):
        """Copy report to clipboard"""
        if not self.preview_text.get(1.0, tk.END).strip():
            messagebox.showwarning("No Data", "Generate a report first")
            return
            
        self.master.clipboard_clear()
        self.master.clipboard_append(self.preview_text.get(1.0, tk.END))
        self.status_var.set("Report copied to clipboard")
        messagebox.showinfo("Success", "Report copied to clipboard!")
        
    def print_report(self):
        """Print the report"""
        messagebox.showinfo("Info", "Print functionality - Coming soon!")

def main():
    root = tk.Tk()
    app = CallReportGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()