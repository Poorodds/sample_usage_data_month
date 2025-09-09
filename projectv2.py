import pandas as pd
from datetime import datetime, time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

uploadedDf = None  # global dataframe

# ---------------- Helper Functions ----------------
def uploadData():
    global uploadedDf
    filePath = filedialog.askopenfilename(filetypes=[("CSV","*.csv"),("Excel","*.xlsx")])
    if not filePath:
        return
    if filePath.endswith(".csv"):
        uploadedDf = pd.read_csv(filePath)
    else:
        uploadedDf = pd.read_excel(filePath)
    uploadedDf["timestamp"] = pd.to_datetime(uploadedDf["timestamp"])
    messagebox.showinfo("Upload","Data uploaded successfully!")

def visualizeBillBreakdown(frame, bill, chartType="bar"):
    for widget in frame.winfo_children():
        widget.destroy()
    breakdown = bill.get("breakdown",{})
    if not breakdown:
        messagebox.showwarning("Error","No breakdown available")
        return
    labels = list(breakdown.keys())
    values = list(breakdown.values())
    fig, ax = plt.subplots(figsize=(max(6,len(labels)*1.5),5))
    if chartType=="bar":
        ax.bar(labels, values, color="skyblue")
        ax.set_ylabel("Cost ($)")
        ax.set_title("Bill Breakdown")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
    else:
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title("Bill Breakdown")
    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.get_tk_widget().pack(fill="both", expand=True)
    canvas.draw()

def visualizeUsage(frame, df):
    for widget in frame.winfo_children():
        widget.destroy()
    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(df["timestamp"], df["kWh"], color="orange")
    ax.set_title("Electricity Usage Trend")
    ax.set_xlabel("Time")
    ax.set_ylabel("kWh")
    fig.autofmt_xdate()
    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.get_tk_widget().pack(fill="both", expand=True)
    canvas.draw()

# ---------------- Tariff Calculations ----------------
def flatRateTariff(df, rate, fixed):
    total = df["kWh"].sum()
    energy = total*rate
    return {"totalBill": energy+fixed,"breakdown":{"Energy":energy,"Fixed Fee":fixed}}

def touTariff(df, rates, fixed):
    breakdown={}
    for _,row in df.iterrows():
        ts = row["timestamp"].time()
        kWh = row["kWh"]
        applied=False
        for period, info in rates.items():
            if "default" in info and info["default"]: continue
            if info["start"]<info["end"]:
                if info["start"]<=ts<info["end"]: breakdown[period]=breakdown.get(period,0)+kWh*info["rate"]; applied=True; break
            else:
                if ts>=info["start"] or ts<info["end"]: breakdown[period]=breakdown.get(period,0)+kWh*info["rate"]; applied=True; break
        if not applied:
            for period, info in rates.items():
                if "default" in info and info["default"]: breakdown[period]=breakdown.get(period,0)+kWh*info["rate"]
    breakdown["Fixed Fee"]=fixed
    total=sum(breakdown.values())
    return {"totalBill":total,"breakdown":breakdown}

def tieredTariff(df, tiers, fixed):
    total=df["kWh"].sum()
    remaining=total; prev=0; breakdown={}; cost=0
    for i,tier in enumerate(tiers,start=1):
        limit=tier["limit"]; rate=tier["rate"]
        if limit is None or remaining<=(limit-prev):
            used=remaining; tierCost=used*rate; breakdown[f"Tier {i}"]=tierCost; cost+=tierCost; break
        else:
            used=limit-prev; tierCost=used*rate; breakdown[f"Tier {i}"]=tierCost; cost+=tierCost; remaining-=used; prev=limit
    breakdown["Fixed Fee"]=fixed
    return {"totalBill":cost+fixed,"breakdown":breakdown}

# ---------------- GUI ----------------
root = tk.Tk()
root.title("XPower Household Tariff Analysis")
root.geometry("1000x750")

notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill="both")

# --- Scrollable frame helper ---
def createScrollFrame(parent):
    container=tk.Frame(parent)
    canvas=tk.Canvas(container)
    scrollbar=tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollFrame=tk.Frame(canvas)
    scrollFrame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0,0), window=scrollFrame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    container.pack(fill="both", expand=True)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return scrollFrame

# --- Upload Tab ---
uploadTab = ttk.Frame(notebook)
notebook.add(uploadTab, text="Upload Data")
ttk.Button(uploadTab, text="Upload CSV/Excel", command=uploadData).pack(pady=20)

# --- Flat Rate Tab ---
flatTab = ttk.Frame(notebook)
notebook.add(flatTab, text="Flat Rate Tariff")
flatFrame = createScrollFrame(flatTab)
ttk.Label(flatFrame, text="Flat Rate ($/kWh)").pack()
flatEntry = ttk.Entry(flatFrame); flatEntry.pack()
ttk.Label(flatFrame, text="Fixed Fee ($)").pack()
flatFeeEntry = ttk.Entry(flatFrame); flatFeeEntry.pack()
flatResultFrame = ttk.Frame(flatFrame)
flatResultFrame.pack(fill="both",expand=True,pady=10)

def calcFlat():
    if uploadedDf is None: messagebox.showwarning("No Data","Upload first"); return
    bill=flatRateTariff(uploadedDf,float(flatEntry.get()),float(flatFeeEntry.get()))
    visualizeBillBreakdown(flatResultFrame,bill,"bar")
ttk.Button(flatFrame, text="Calculate & Visualize", command=calcFlat).pack(pady=10)

# --- TOU Tab ---
touTab = ttk.Frame(notebook)
notebook.add(touTab, text="TOU Tariff")
touFrame=createScrollFrame(touTab)
# TOU entries
labels=["Peak Start","Peak End","Peak Rate","Off-Peak Start","Off-Peak End","Off-Peak Rate","Shoulder Rate","Fixed Fee"]
touEntries=[]
for l in labels: ttk.Label(touFrame,text=l).pack(); e=ttk.Entry(touFrame); e.pack(); touEntries.append(e)
touResultFrame=ttk.Frame(touFrame); touResultFrame.pack(fill="both",expand=True,pady=10)
def calcTOU():
    if uploadedDf is None: messagebox.showwarning("No Data","Upload first"); return
    peakStart=datetime.strptime(touEntries[0].get(),"%H:%M").time()
    peakEnd=datetime.strptime(touEntries[1].get(),"%H:%M").time()
    peakRate=float(touEntries[2].get())
    offStart=datetime.strptime(touEntries[3].get(),"%H:%M").time()
    offEnd=datetime.strptime(touEntries[4].get(),"%H:%M").time()
    offRate=float(touEntries[5].get())
    shoulderRate=float(touEntries[6].get())
    fee=float(touEntries[7].get())
    rates={"Peak":{"start":peakStart,"end":peakEnd,"rate":peakRate},
           "Off-Peak":{"start":offStart,"end":offEnd,"rate":offRate},
           "Shoulder":{"default":True,"rate":shoulderRate}}
    bill=touTariff(uploadedDf,rates,fee)
    visualizeBillBreakdown(touResultFrame,bill,"bar")
ttk.Button(touFrame,text="Calculate & Visualize",command=calcTOU).pack(pady=10)

# --- Tiered Tab ---
tierTab = ttk.Frame(notebook)
notebook.add(tierTab,text="Tiered Tariff")
tierFrame=createScrollFrame(tierTab)
tierLimits=[]; tierRates=[]
for i in range(3):
    ttk.Label(tierFrame,text=f"Tier {i+1} Upper Limit (blank=unlimited)").pack()
    l=ttk.Entry(tierFrame); l.pack(); tierLimits.append(l)
    ttk.Label(tierFrame,text=f"Tier {i+1} Rate ($/kWh)").pack()
    r=ttk.Entry(tierFrame); r.pack(); tierRates.append(r)
ttk.Label(tierFrame,text="Fixed Fee ($)").pack()
tierFeeEntry=ttk.Entry(tierFrame); tierFeeEntry.pack()
tierResultFrame=ttk.Frame(tierFrame); tierResultFrame.pack(fill="both",expand=True,pady=10)
def calcTier():
    if uploadedDf is None: messagebox.showwarning("No Data","Upload first"); return
    tiers=[]
    for l,r in zip(tierLimits,tierRates):
        limit=l.get(); rate=float(r.get())
        limit=int(limit) if limit else None
        tiers.append({"limit":limit,"rate":rate})
    fee=float(tierFeeEntry.get())
    bill=tieredTariff(uploadedDf,tiers,fee)
    visualizeBillBreakdown(tierResultFrame,bill,"bar")
ttk.Button(tierFrame,text="Calculate & Visualize",command=calcTier).pack(pady=10)

# --- Comparison & Usage Tab ---
compareTab=ttk.Frame(notebook)
notebook.add(compareTab,text="Bill Comparison & Usage Trend")
compareFrame=createScrollFrame(compareTab)
compareResultFrame=ttk.Frame(compareFrame); compareResultFrame.pack(fill="both",expand=True,pady=10)
def calcComparison():
    if uploadedDf is None: messagebox.showwarning("No Data","Upload first"); return
    bills={}
    # flat
    bills["Flat"]=flatRateTariff(uploadedDf,float(flatEntry.get()),float(flatFeeEntry.get()))
    # TOU
    peakStart=datetime.strptime(touEntries[0].get(),"%H:%M").time()
    peakEnd=datetime.strptime(touEntries[1].get(),"%H:%M").time()
    peakRate=float(touEntries[2].get())
    offStart=datetime.strptime(touEntries[3].get(),"%H:%M").time()
    offEnd=datetime.strptime(touEntries[4].get(),"%H:%M").time()
    offRate=float(touEntries[5].get())
    shoulderRate=float(touEntries[6].get())
    fee=float(touEntries[7].get())
    rates={"Peak":{"start":peakStart,"end":peakEnd,"rate":peakRate},
           "Off-Peak":{"start":offStart,"end":offEnd,"rate":offRate},
           "Shoulder":{"default":True,"rate":shoulderRate}}
    bills["TOU"]=touTariff(uploadedDf,rates,fee)
    # Tiered
    tiers=[]
    for l,r in zip(tierLimits,tierRates):
        limit=l.get(); rate=float(r.get())
        limit=int(limit) if limit else None
        tiers.append({"limit":limit,"rate":rate})
    fee=float(tierFeeEntry.get())
    bills["Tiered"]=tieredTariff(uploadedDf,tiers,fee)
    # Find cheapest
    cheapest=min(bills,key=lambda k: bills[k]["totalBill"])
    msg="\n".join([f"{k}: ${v['totalBill']:.2f}{' ✅ Cheapest' if k==cheapest else ''}" for k,v in bills.items()])
    messagebox.showinfo("Comparison Result",msg)
    # Visualize total comparison
    for widget in compareResultFrame.winfo_children(): widget.destroy()
    fig, ax=plt.subplots(figsize=(max(6,len(bills)*2),4))
    ax.bar(bills.keys(), [b["totalBill"] for b in bills.values()], color=["skyblue","lightgreen","salmon"])
    ax.set_ylabel("Total Bill ($)"); ax.set_title("Total Bill Comparison")
    canvas=FigureCanvasTkAgg(fig, master=compareResultFrame)
    canvas.get_tk_widget().pack(fill="both",expand=True)
    canvas.draw()
    # Usage trend below
    usageFrame=ttk.Frame(compareResultFrame); usageFrame.pack(fill="both",expand=True,pady=20)
    visualizeUsage(usageFrame,uploadedDf)
ttk.Button(compareFrame,text="Calculate & Compare All Tariffs",command=calcComparison).pack(pady=10)

# --- Exit Tab ---
exitTab=ttk.Frame(notebook)
notebook.add(exitTab,text="Exit")
ttk.Button(exitTab,text="Exit Application",command=root.destroy).pack(pady=20)

root.mainloop()
