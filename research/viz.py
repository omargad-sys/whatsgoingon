import pandas as pd
import matplotlib.pyplot as plt

panel = pd.read_csv("monthly_panel_full.csv")

panel["year_month"] = pd.to_datetime(panel["year_month"])

countries = sorted(panel["country"].unique())

fig, axes = plt.subplots(len(countries), 1, figsize=(12, 2.5 * len(countries)), sharex=True)

for ax, country in zip(axes, countries):
    sub = panel[panel["country"] == country].sort_values("year_month")
    ax.plot(sub["year_month"], sub["num_events"], color="steelblue", linewidth=1.5)
    ax.set_title(country, loc="left", fontsize=11)
    ax.set_ylabel("events / month")
    ax.grid(alpha=0.3)

axes[-1].set_xlabel("month")
fig.suptitle("Monthly conflict events by country, 2018-2024", fontsize =14, y=1.002)
plt.tight_layout()

plt.savefig("events_by_country.png",dpi=120, bbox_inches="tight")
plt.show()

print("Saved events_by_country.png")
