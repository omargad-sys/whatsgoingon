"""Pipeline unit tests. Standard library only:

    cd research && python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aggregate import fill_missing_months, to_monthly  # noqa: E402
from build_sensitivities import benjamini_hochberg  # noqa: E402
from build_snapshot import build_heat, build_top_events, clean, week_starts  # noqa: E402
from intensity import theme_levels, theme_shocks  # noqa: E402
from ols import ols_hac  # noqa: E402
from universe import COUNTRIES, THEMES, TICKERS  # noqa: E402


def sample_events():
    return pd.DataFrame(
        {
            "event_date": ["2024-01-05", "2024-01-20", "2024-02-11", "2024-02-12", None, "2024-03-01"],
            "country": ["Yemen", "Yemen", "Yemen", "Yemen", "Yemen", "Sudan"],
            "event_type": ["Battles", "Protests", "Battles", "Violence against civilians", "Battles", "Battles"],
            # ACLED really does hand back fatalities as strings, including "".
            "fatalities": ["3", "0", "not-a-number", "7", "1", ""],
            "latitude": [15.3, 15.4, 15.5, 0.0, 15.6, 15.7],
            "longitude": [44.2, 44.3, 44.4, 0.0, 44.5, 32.5],
            "sub_event_type": ["Armed clash"] * 6,
            "location": ["L"] * 6,
        }
    )


class TestAggregate(unittest.TestCase):
    def test_drops_null_dates_and_coerces_fatalities(self):
        monthly = to_monthly(sample_events())
        jan = monthly[(monthly.country == "Yemen") & (monthly.year_month == "2024-01-01")].iloc[0]
        self.assertEqual(jan.num_events, 2)
        self.assertEqual(jan.total_fatalities, 3)

        feb = monthly[(monthly.country == "Yemen") & (monthly.year_month == "2024-02-01")].iloc[0]
        # "not-a-number" must become 0, not propagate NaN into the sum.
        self.assertEqual(feb.total_fatalities, 7)
        self.assertEqual(feb.num_events, 2)

        # The row with a null event_date is dropped entirely.
        self.assertEqual(int(monthly[monthly.country == "Yemen"].num_events.sum()), 4)

    def test_event_type_counters(self):
        monthly = to_monthly(sample_events())
        jan = monthly[(monthly.country == "Yemen") & (monthly.year_month == "2024-01-01")].iloc[0]
        self.assertEqual(jan.battles, 1)
        self.assertEqual(jan.protests, 1)
        self.assertEqual(jan.violence_civilians, 0)

    def test_fill_missing_months_inserts_zeros(self):
        panel = to_monthly(sample_events())
        filled = fill_missing_months(panel)
        # 2 countries x 3 months (Jan-Mar) with no gaps.
        self.assertEqual(len(filled), 6)
        sudan_jan = filled[(filled.country == "Sudan") & (filled.year_month == "2024-01-01")].iloc[0]
        self.assertEqual(sudan_jan.num_events, 0)
        self.assertEqual(sudan_jan.total_fatalities, 0)


class TestSnapshot(unittest.TestCase):
    def test_clean_drops_null_island_and_bad_coords(self):
        df = clean(sample_events())
        # Drops the null date row and the 0,0 placeholder row.
        self.assertEqual(len(df), 4)
        self.assertFalse(((df.latitude.abs() < 1e-6) & (df.longitude.abs() < 1e-6)).any())

    def test_heat_preserves_totals(self):
        df = clean(sample_events())
        weeks, idx = week_starts(df)
        heat = build_heat(df, weeks, idx)
        total_events = sum(c[3] for c in heat["cells"])
        total_fatal = sum(c[4] for c in heat["cells"])
        self.assertEqual(total_events, len(df))
        self.assertEqual(total_fatal, int(df.fatalities.sum()))

    def test_heat_cell_centres_land_inside_their_bin(self):
        df = clean(sample_events())
        weeks, idx = week_starts(df)
        heat = build_heat(df, weeks, idx)
        size = heat["cell_size"]
        for _, lon, lat, _, _ in heat["cells"]:
            # Centre must be offset by exactly half a cell from a bin edge.
            self.assertAlmostEqual((lon - size / 2) % size, 0.0, places=6)
            self.assertAlmostEqual((lat - size / 2) % size, 0.0, places=6)

    def test_top_events_geojson_shape(self):
        df = clean(sample_events())
        weeks, idx = week_starts(df)
        fc = build_top_events(df, idx)
        self.assertEqual(fc["type"], "FeatureCollection")
        for f in fc["features"]:
            lon, lat = f["geometry"]["coordinates"]
            self.assertTrue(-180 <= lon <= 180)
            self.assertTrue(-90 <= lat <= 90)
            self.assertIn("f", f["properties"])
            self.assertIsInstance(f["properties"]["f"], int)
            self.assertLess(f["properties"]["w"], len(weeks))


class TestIntensity(unittest.TestCase):
    def _panel(self, months=120, level=100.0):
        rows = []
        dates = pd.date_range("2016-01-01", periods=months, freq="MS")
        for c in ["Iran", "Iraq", "Ukraine"]:
            for d in dates:
                rows.append(
                    {
                        "country": c,
                        "year_month": d.strftime("%Y-%m-%d"),
                        "num_events": level,
                        "total_fatalities": level / 2,
                        "battles": 0,
                        "protests": 0,
                        "violence_civilians": 0,
                    }
                )
        return pd.DataFrame(rows)

    def test_constant_panel_produces_no_spurious_shock(self):
        z = theme_shocks(self._panel())
        # A perfectly flat series has zero shock variance, so the z-score is
        # undefined. It must come out NaN, never a divide-by-zero infinity and
        # never a finite non-zero value that the UI would present as a signal.
        col = z["oil_supply"]
        self.assertTrue(col.isna().all(), f"expected all-NaN, got {col.dropna().unique()[:5]}")
        self.assertFalse(np.isinf(col.to_numpy(dtype=float)).any())

    def test_levels_are_log_damped(self):
        small = theme_levels(self._panel(level=100.0))["oil_supply"].iloc[-1]
        big = theme_levels(self._panel(level=10000.0))["oil_supply"].iloc[-1]
        # 100x the events must not be 100x the index.
        self.assertLess(big / small, 3.0)
        self.assertGreater(big, small)

    def test_shocks_are_clipped(self):
        rng = np.random.default_rng(3)
        dates = pd.date_range("2015-01-01", periods=140, freq="MS")
        rows = []
        for i, d in enumerate(dates):
            # A single 10000x spike that would blow past 4 sigma uncapped.
            spike = 1_000_000 if i == 130 else int(rng.integers(50, 150))
            rows.append(
                {
                    "country": "Iran",
                    "year_month": d.strftime("%Y-%m-%d"),
                    "num_events": spike,
                    "total_fatalities": 0,
                    "battles": 0,
                    "protests": 0,
                    "violence_civilians": 0,
                }
            )
        z = theme_shocks(pd.DataFrame(rows))["oil_supply"].dropna()
        self.assertLessEqual(z.abs().max(), 4.0 + 1e-9)


class TestOLS(unittest.TestCase):
    def test_recovers_planted_coefficients(self):
        rng = np.random.default_rng(101)
        n = 500
        x1, x2 = rng.normal(size=n), rng.normal(size=n)
        y = 0.25 + 1.75 * x1 - 0.90 * x2 + rng.normal(scale=0.4, size=n)
        fit = ols_hac(y, np.column_stack([x1, x2]), ["x1", "x2"])
        self.assertAlmostEqual(fit.get("x1")["beta"], 1.75, delta=0.05)
        self.assertAlmostEqual(fit.get("x2")["beta"], -0.90, delta=0.05)
        self.assertGreater(abs(fit.get("x1")["tstat"]), 10)

    def test_sign_is_not_flipped(self):
        rng = np.random.default_rng(7)
        x = rng.normal(size=300)
        fit = ols_hac(-2.0 * x + rng.normal(scale=0.2, size=300), x.reshape(-1, 1), ["x"])
        self.assertLess(fit.get("x")["beta"], 0)

    def test_null_relationship_stays_below_threshold(self):
        rng = np.random.default_rng(4242)
        below = 0
        for _ in range(40):
            x, y = rng.normal(size=200), rng.normal(size=200)
            if abs(ols_hac(y, x.reshape(-1, 1), ["x"]).get("x")["tstat"]) < 2.0:
                below += 1
        # Nominal 5% rejection rate; allow slack but catch a broken SE formula.
        self.assertGreaterEqual(below, 34)

    def test_hac_se_exceeds_naive_se_under_autocorrelation(self):
        rng = np.random.default_rng(9)
        n = 300
        x = np.zeros(n)
        e = np.zeros(n)
        for i in range(1, n):
            x[i] = 0.9 * x[i - 1] + rng.normal()
            e[i] = 0.9 * e[i - 1] + rng.normal()
        fit_hac = ols_hac(e, x.reshape(-1, 1), ["x"], lags=8)
        fit_naive = ols_hac(e, x.reshape(-1, 1), ["x"], lags=0)
        self.assertGreater(fit_hac.get("x")["se"], fit_naive.get("x")["se"])

    def test_rejects_degenerate_sample(self):
        with self.assertRaises(ValueError):
            ols_hac(np.arange(3.0), np.arange(3.0).reshape(-1, 1), ["x"])


class TestFDR(unittest.TestCase):
    def test_controls_error_rate_under_the_global_null(self):
        # BH does not promise zero discoveries on any single all-null draw; it
        # promises the false discovery rate stays at or below q. Under the
        # global null that reduces to P(any discovery) <= q, which is a claim
        # about replications, not about one seed.
        rng = np.random.default_rng(5)
        trials = 400
        with_discovery = sum(
            1 for _ in range(trials) if benjamini_hochberg(rng.uniform(size=50), q=0.10).any()
        )
        rate = with_discovery / trials
        self.assertLessEqual(rate, 0.16, f"FDR gate too permissive: {rate:.3f} of null draws fired")

    def test_strong_signals_survive(self):
        p = np.array([1e-6, 1e-5, 1e-4] + list(np.linspace(0.2, 0.99, 47)))
        self.assertGreaterEqual(benjamini_hochberg(p, q=0.10).sum(), 3)

    def test_is_never_more_permissive_than_raw_alpha(self):
        rng = np.random.default_rng(6)
        p = rng.uniform(size=200)
        self.assertLessEqual(benjamini_hochberg(p, q=0.05).sum(), (p <= 0.05).sum())

    def test_empty_input(self):
        self.assertEqual(len(benjamini_hochberg([])), 0)


class TestUniverseConsistency(unittest.TestCase):
    def test_every_theme_member_is_in_the_universe(self):
        for theme_id, meta in THEMES.items():
            for country in meta["countries"]:
                self.assertIn(country, COUNTRIES, f"{theme_id} references unknown country {country}")

    def test_geo_covers_every_country(self):
        from geo import CENTROIDS

        for country in COUNTRIES:
            self.assertIn(country, CENTROIDS, f"missing centroid for {country}")

    def test_spy_present_for_market_control(self):
        self.assertIn("SPY", TICKERS)


if __name__ == "__main__":
    unittest.main()


class TestTargetLeakage(unittest.TestCase):
    """The label must not see the future beyond the value it asks about."""

    def _panel(self, fatalities):
        n = len(fatalities)
        dates = pd.date_range("2018-01-01", periods=n, freq="MS")
        return pd.DataFrame(
            {
                "country": ["Iran"] * n,
                "year_month": dates,
                "num_events": [100] * n,
                "total_fatalities": fatalities,
                "battles": [0] * n,
                "protests": [0] * n,
                "violence_civilians": [0] * n,
            }
        )

    def test_threshold_uses_only_the_past(self):
        from features import add_rolling_features, add_target

        calm = [10] * 30
        # Two panels identical up to month 30, then one explodes.
        quiet = add_target(add_rolling_features(self._panel(calm + [10] * 20)))
        spike = add_target(add_rolling_features(self._panel(calm + [99999] * 20)))

        # The threshold at month 20 predates the divergence, so it must match.
        a = quiet[quiet.year_month == "2019-09-01"]["threshold"].iloc[0]
        b = spike[spike.year_month == "2019-09-01"]["threshold"].iloc[0]
        self.assertAlmostEqual(a, b, places=6, msg="future values leaked into the threshold")

    def test_escalated_describes_the_following_month(self):
        from features import add_rolling_features, add_target

        vals = [10] * 24 + [10, 500, 10] + [10] * 10
        d = add_target(add_rolling_features(self._panel(vals))).set_index("year_month")

        spike_month = pd.Timestamp("2020-02-01")   # index 25, the 500
        prior_month = pd.Timestamp("2020-01-01")   # index 24

        # The label on the month BEFORE the spike is the one that should fire.
        self.assertEqual(d.loc[prior_month, "escalated"], 1)
        self.assertEqual(d.loc[spike_month, "escalated"], 0)

    def test_rows_without_a_future_value_are_dropped(self):
        from features import add_rolling_features, add_target

        d = add_target(add_rolling_features(self._panel([10] * 40)))
        self.assertTrue(d["future_fatalities"].notna().all())
        self.assertNotIn(pd.Timestamp("2021-04-01"), set(d["year_month"]))


class TestLinkAlignment(unittest.TestCase):
    """z_T(t+1) must be regressed on frac_esc(T, t), not on frac_esc(T, t+1)."""

    def _panel(self, seed=5):
        rng = np.random.default_rng(seed)
        countries = THEMES["oil_supply"]["countries"][:6]
        dates = pd.date_range("2017-01-01", periods=110, freq="MS")
        rows = []
        for c in countries:
            level = np.exp(np.cumsum(rng.normal(0, 0.12, len(dates)))) * 300
            for d, v in zip(dates, level):
                rows.append(
                    {
                        "country": c,
                        "year_month": d,
                        "num_events": int(v),
                        "total_fatalities": int(v * 0.4),
                        "battles": 0,
                        "protests": 0,
                        "violence_civilians": 0,
                    }
                )
        return pd.DataFrame(rows)

    def test_regression_uses_the_one_month_offset(self):
        from aggregate import fill_missing_months
        from build_link import escalation_fractions, fit_links
        from features import add_rolling_features, add_target
        from intensity import theme_shocks
        from ols import ols_hac

        panel = self._panel()
        labelled = add_target(add_rolling_features(panel))
        links = fit_links(panel, labelled)
        self.assertIn("oil_supply", links)

        shocks = theme_shocks(fill_missing_months(panel))
        fracs = escalation_fractions(labelled)

        correct = pd.DataFrame(
            {"y": shocks["oil_supply"].shift(-1), "x": fracs["oil_supply"]}
        ).dropna()
        expected = ols_hac(correct["y"].to_numpy(), correct[["x"]].to_numpy(), ["x"])

        self.assertEqual(links["oil_supply"]["n"], int(expected.nobs))
        self.assertAlmostEqual(
            links["oil_supply"]["slope"], round(expected.get("x")["beta"], 6), places=6
        )

        # And it must NOT match the un-shifted alignment, which would let a
        # month's violence help predict itself.
        wrong_frame = pd.DataFrame(
            {"y": shocks["oil_supply"], "x": fracs["oil_supply"]}
        ).dropna()
        wrong = ols_hac(wrong_frame["y"].to_numpy(), wrong_frame[["x"]].to_numpy(), ["x"])
        self.assertNotAlmostEqual(
            links["oil_supply"]["slope"], round(wrong.get("x")["beta"], 6), places=4
        )
