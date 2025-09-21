import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

# -----------------------------
# Load data
# -----------------------------
url = "https://raw.githubusercontent.com/Poorodds/sample_usage_data_month/refs/heads/main/sample_usage_data_month.csv"
df = pd.read_csv(url)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# -----------------------------
# Helper functions (safe input)
# -----------------------------
def getFloat(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("⚠ Please enter a valid number.")

def getInt(prompt, allowBlank=False):
    while True:
        userInput = input(prompt)
        if allowBlank and userInput.strip() == "":
            return None
        try:
            return int(userInput)
        except ValueError:
            print("⚠ Please enter a valid integer.")

def getTime(prompt):
    while True:
        userInput = input(prompt)
        try:
            return datetime.strptime(userInput, "%H:%M").time()
        except ValueError:
            print("⚠ Please enter time in HH:MM format (e.g., 18:30).")

def getDate(prompt):
    while True:
        userInput = input(prompt)
        try:
            return datetime.strptime(userInput, "%Y-%m-%d")
        except ValueError:
            print("⚠ Please enter date in YYYY-MM-DD format.")

# -----------------------------
# Tariff Calculations
# -----------------------------
def flatRateTariff(df, flatRate, fixedFee=0):
    totalKWh = df["kWh"].sum()
    energyCost = totalKWh * flatRate
    totalBill = energyCost + fixedFee
    return {
        "totalKWh": totalKWh,
        "breakdown": {"Energy Cost": energyCost},
        "fixedFee": fixedFee,
        "totalBill": totalBill
    }


def touTariff(df, touRates, fixedFee=0):
    breakdown = {}
    for _, row in df.iterrows():
        ts = row["timestamp"].time()
        kWh = row["kWh"]
        applied = False

        for period, info in touRates.items():
            if "default" in info and info["default"]:
                continue
            if info["start"] < info["end"]:
                if info["start"] <= ts < info["end"]:
                    breakdown[period] = breakdown.get(period, 0) + kWh * info["rate"]
                    applied = True
                    break
            else:
                if ts >= info["start"] or ts < info["end"]:
                    breakdown[period] = breakdown.get(period, 0) + kWh * info["rate"]
                    applied = True
                    break
        if not applied:
            for period, info in touRates.items():
                if "default" in info and info["default"]:
                    breakdown[period] = breakdown.get(period, 0) + kWh * info["rate"]
    total = sum(breakdown.values()) + fixedFee
    return {"breakdown": breakdown, "fixedFee": fixedFee, "totalBill": total}

def tieredTariff(df, tiers, fixedFee=0):
    totalKWh = df["kWh"].sum()
    remaining = totalKWh
    previousLimit = 0
    breakdown = []
    cost = 0
    for tier in tiers:
        limit = tier["limit"]
        rate = tier["rate"]
        if limit is None or remaining <= (limit - previousLimit):
            used = remaining
            tierCost = used * rate
            breakdown.append({"used": used, "rate": rate, "cost": tierCost})
            cost += tierCost
            break
        else:
            used = limit - previousLimit
            tierCost = used * rate
            breakdown.append({"used": used, "rate": rate, "cost": tierCost})
            cost += tierCost
            remaining -= used
            previousLimit = limit
    totalBill = cost + fixedFee
    return {"totalKWh": totalKWh, "breakdown": breakdown, "fixedFee": fixedFee, "totalBill": totalBill}

def filterDataByDuration(df, startDate, endDate):
    mask = (df["timestamp"] >= startDate) & (df["timestamp"] <= endDate)
    return df.loc[mask]

def calculateBills(df, tariffs):
    results = {}
    if "flat" in tariffs:
        r = tariffs["flat"]
        results["Flat Rate"] = flatRateTariff(df, r["rate"], r["fixedFee"])
    if "tou" in tariffs:
        r = tariffs["tou"]
        results["TOU"] = touTariff(df, r["rates"], r["fixedFee"])
    if "tiered" in tariffs:
        r = tariffs["tiered"]
        results["Tiered"] = tieredTariff(df, r["tiers"], r["fixedFee"])
    return results

def compareBills(bills):
    print("\n--- Bill Comparison ---")
    minScheme = min(bills, key=lambda k: bills[k]["totalBill"])
    minValue = bills[minScheme]["totalBill"]
    for scheme, result in bills.items():
        total = result["totalBill"]
        diff = total - minValue
        savingNote = "✅ Cheapest" if scheme == minScheme else f"(${diff:.2f} more)"
        print(f"{scheme:10} | Total Bill: ${total:.2f} {savingNote}")

# -----------------------------
# Visualization
# -----------------------------
def visualizeBillBreakdown(billResult, chartType="bar"):
    breakdown = billResult.get("breakdown", {})
    if isinstance(breakdown, list):
        breakdownDict = {f"Tier {i+1}": b["cost"] for i, b in enumerate(breakdown)}
    elif isinstance(breakdown, dict):
        breakdownDict = breakdown.copy()
    else:
        print("⚠ Unsupported breakdown format.")
        return
    breakdownDict["Fixed Fee"] = billResult.get("fixedFee", 0)

    labels = list(breakdownDict.keys())
    values = list(breakdownDict.values())

    plt.figure(figsize=(6, 6))
    if chartType == "bar":
        plt.bar(labels, values)
        plt.title("Bill Breakdown (Bar Chart)")
        plt.ylabel("Cost ($)")
        plt.xticks(rotation=45)
    else:
        plt.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        plt.title("Bill Breakdown (Pie Chart)")
    plt.tight_layout()
    plt.show()

def visualizeUsage(dfFiltered, startDate, endDate):
    dfPlot = dfFiltered.copy()
    plt.figure(figsize=(10, 4))
    plt.plot(dfPlot["timestamp"], dfPlot["kWh"], marker="o", linestyle="-")
    plt.title(f"Electricity Usage: {startDate.date()} to {endDate.date()}")
    plt.xlabel("Timestamp")
    plt.ylabel("kWh")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# -----------------------------
# Bill Comparison Menu
# -----------------------------
def billComparisonMenu(df):
    startDate = getDate("Enter start date (YYYY-MM-DD): ")
    endDate = getDate("Enter end date (YYYY-MM-DD): ")
    dfFiltered = filterDataByDuration(df, startDate, endDate)
    if dfFiltered.empty:
        print("⚠ No data in this range!")
        return None

    print("\n--- Define Tariffs for Comparison ---")
    flatRate = getFloat("Flat rate ($/kWh): ")
    flatFee = getFloat("Flat fixed fee ($): ")

    print("\nTOU settings:")
    peakStart = getTime("Peak start (HH:MM): ")
    peakEnd = getTime("Peak end (HH:MM): ")
    peakRate = getFloat("Peak rate ($/kWh): ")

    offStart = getTime("Off-peak start (HH:MM): ")
    offEnd = getTime("Off-peak end (HH:MM): ")
    offRate = getFloat("Off-peak rate ($/kWh): ")

    shoulderRate = getFloat("Shoulder rate ($/kWh): ")
    touFee = getFloat("TOU fixed fee ($): ")

    touRates = {
        "Peak": {"start": peakStart, "end": peakEnd, "rate": peakRate},
        "Off-Peak": {"start": offStart, "end": offEnd, "rate": offRate},
        "Shoulder": {"default": True, "rate": shoulderRate}
    }

    tiers = []
    numTiers = getInt("Number of tiers: ")
    for i in range(numTiers):
        limit = getInt(f"Tier {i+1} upper limit (blank = unlimited): ", allowBlank=True)
        rate = getFloat(f"Tier {i+1} rate ($/kWh): ")
        tiers.append({"limit": limit, "rate": rate})
    tieredFee = getFloat("Tiered fixed fee ($): ")

    tariffs = {
        "flat": {"rate": flatRate, "fixedFee": flatFee},
        "tou": {"rates": touRates, "fixedFee": touFee},
        "tiered": {"tiers": tiers, "fixedFee": tieredFee}
    }

    bills = calculateBills(dfFiltered, tariffs)
    compareBills(bills)

    minScheme = min(bills, key=lambda k: bills[k]["totalBill"])
    print(f"\nVisualizing cheapest bill: {minScheme}")
    visualizeBillBreakdown(bills[minScheme], chartType="bar")
    return bills

# -----------------------------
# Visualization Menu
# -----------------------------
def visualizationMenu(df):
    startDate = getDate("Enter start date (YYYY-MM-DD): ")
    endDate = getDate("Enter end date (YYYY-MM-DD): ")
    dfFiltered = filterDataByDuration(df, startDate, endDate)
    if dfFiltered.empty:
        print("⚠ No data in this range!")
        return

    visualizeUsage(dfFiltered, startDate, endDate)

    print("\nChoose a tariff model for bill breakdown:")
    print("1. Flat Rate")
    print("2. TOU")
    print("3. Tiered")
    choice = input("Choice (1-3): ").strip()

    if choice == "1":
        rate = getFloat("Flat rate ($/kWh): ")
        fee = getFloat("Fixed fee ($): ")
        bill = flatRateTariff(dfFiltered, rate, fee)
    elif choice == "2":
        print("\nTOU settings:")
        peakStart = getTime("Peak start (HH:MM): ")
        peakEnd = getTime("Peak end (HH:MM): ")
        peakRate = getFloat("Peak rate ($/kWh): ")

        offStart = getTime("Off-peak start (HH:MM): ")
        offEnd = getTime("Off-peak end (HH:MM): ")
        offRate = getFloat("Off-peak rate ($/kWh): ")

        shoulderRate = getFloat("Shoulder rate ($/kWh): ")
        fee = getFloat("Fixed fee ($): ")

        touRates = {
            "Peak": {"start": peakStart, "end": peakEnd, "rate": peakRate},
            "Off-Peak": {"start": offStart, "end": offEnd, "rate": offRate},
            "Shoulder": {"default": True, "rate": shoulderRate}
        }
        bill = touTariff(dfFiltered, touRates, fee)
    elif choice == "3":
        tiers = []
        numTiers = getInt("Number of tiers: ")
        for i in range(numTiers):
            limit = getInt(f"Tier {i+1} upper limit (blank = unlimited): ", allowBlank=True)
            rate = getFloat(f"Tier {i+1} rate ($/kWh): ")
            tiers.append({"limit": limit, "rate": rate})
        fee = getFloat("Fixed fee ($): ")
        bill = tieredTariff(dfFiltered, tiers, fee)
    else:
        print("⚠ Invalid choice.")
        return

    visualizeBillBreakdown(bill, chartType="bar")

# -----------------------------
# Main Menu
# -----------------------------
def main():
    while True:
        print("\n--- Electricity Tariff Calculator ---")
        print("1. Flat Rate Tariff")
        print("2. Time-of-Use (TOU) Tariff")
        print("3. Tiered (Block) Tariff")
        print("4. Bill Calculation & Comparison")
        print("5. Usage Trend & Bill Visualization")
        print("6. Exit")

        choice = input("Choose option (1-6): ").strip()
        if choice == "1":
            flatRate = getFloat("Enter flat rate ($/kWh): ")
            fixedFee = getFloat("Enter fixed monthly fee ($): ")
            result = flatRateTariff(df, flatRate, fixedFee)
            print("\n--- Flat Rate Tariff Bill ---")
            print(result)
            visualizeBillBreakdown(result, "bar")
        elif choice == "2":
            print("\nDefine TOU Rates:")
            peakStart = getTime("Peak start (HH:MM): ")
            peakEnd = getTime("Peak end (HH:MM): ")
            peakRate = getFloat("Peak rate ($/kWh): ")

            offStart = getTime("Off-Peak start (HH:MM): ")
            offEnd = getTime("Off-Peak end (HH:MM): ")
            offRate = getFloat("Off-Peak rate ($/kWh): ")

            shoulderRate = getFloat("Shoulder rate ($/kWh): ")
            fixedFee = getFloat("Fixed monthly fee ($): ")

            touRates = {
                "Peak": {"start": peakStart, "end": peakEnd, "rate": peakRate},
                "Off-Peak": {"start": offStart, "end": offEnd, "rate": offRate},
                "Shoulder": {"default": True, "rate": shoulderRate}
            }
            result = touTariff(df, touRates, fixedFee)
            print("\n--- TOU Tariff Bill ---")
            print(result)
            visualizeBillBreakdown(result, "bar")
        elif choice == "3":
            print("\nDefine Tiered Rates:")
            numTiers = getInt("Number of tiers: ")
            tiers = []
            for i in range(numTiers):
                limit = getInt(f"Upper limit Tier {i+1} (blank = unlimited): ", allowBlank=True)
                rate = getFloat(f"Rate Tier {i+1} ($/kWh): ")
                tiers.append({"limit": limit, "rate": rate})
            fixedFee = getFloat("Fixed monthly fee ($): ")
            result = tieredTariff(df, tiers, fixedFee)
            print("\n--- Tiered Tariff Bill ---")
            print(result)
            visualizeBillBreakdown(result, "bar")
        elif choice == "4":
            billComparisonMenu(df)
        elif choice == "5":
            visualizationMenu(df)
        elif choice == "6":
            print("Exiting program. Goodbye!")
            break
        else:
            print("⚠ Invalid choice, please try again.")

# -----------------------------
# Run Program
# -----------------------------
if __name__ == "__main__":
    main()
