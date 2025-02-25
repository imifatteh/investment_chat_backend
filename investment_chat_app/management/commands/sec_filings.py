import csv
import os
import requests

from datetime import datetime
from django.conf import settings
from django.core.management import BaseCommand

from investment_chat_app.models import SECFilings

SEC_API_URL = settings.SEC_API_URL
SEC_API_KEY = settings.SEC_API_KEY
PDF_SAVE_PATH = "investment_chat_app/SEC_FILINGS"
PDF_CONV_URL = settings.PDF_CONV_URL


class Command(BaseCommand):
    """Custom Django management command to fetch and download SEC filings."""

    help = "Fetch and download SEC filings for S&P 500 companies from a CSV file and store metadata in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--form-type",
            type=str,
            default="10-K",
            help="Type of filing to fetch (default: 10-K).",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=datetime.now().year,
            help="Year of the filing to fetch (default: 2020).",
        )

    def handle(self, *args, **options):
        form_type = options["form_type"]
        year = options["year"]

        os.makedirs(PDF_SAVE_PATH, exist_ok=True)

        file_path = os.path.join(
            settings.BASE_DIR, "investment_chat_app/utils/constituents.csv"
        )
        with open(file_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                ticker = row.get("Symbol")

                if not ticker:
                    self.stderr.write(
                        self.style.WARNING("⚠️ Skipping row with missing ticker.")
                    )
                    continue

                self.stdout.write(
                    self.style.SUCCESS(f"✅ Processing {ticker} ({form_type}, {year})")
                )

                filings = self.fetch_sec_filings(ticker, form_type, year)

                if filings:
                    for filing in filings:
                        self.download_and_store_filing(filing, ticker, form_type, year)
                else:
                    self.stderr.write(
                        self.style.WARNING(f"⚠️ No filings found for {ticker}.")
                    )

    def fetch_sec_filings(self, ticker, form_type, year):
        """Fetch SEC Filings for a given ticker, form type, and year."""
        query = {
            "query": {
                "query_string": {
                    "query": f'ticker:{ticker} AND formType:"{form_type}" AND filedAt:[{year}-01-01 TO {year}-12-31]'
                }
            },
            "from": 0,
            "size": 5,
            "sort": [{"filedAt": {"order": "desc"}}],
        }

        response = requests.post(
            SEC_API_URL, json=query, headers={"Authorization": SEC_API_KEY}
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("filings", [])
        else:
            self.stderr.write(
                self.style.ERROR(
                    f"❌ Failed to fetch filings for {ticker}. Status Code: {response.status_code}"
                )
            )
            return None

    def download_and_store_filing(self, filing, ticker, form_type, year):
        """Downloads the filing PDF and stores metadata in the database."""
        filing_url = filing.get("linkToFilingDetails")
        ticker = filing.get("ticker")
        filing_date = filing.get("filedAt")

        if not filing_url:
            self.stderr.write(
                self.style.WARNING(f"Skipping {ticker}: No filing URL found.")
            )
            return

        # Convert filing to PDF
        pdf_conv_url = (
            f"https://api.sec-api.io/filing-reader?token={SEC_API_KEY}&url={filing_url}"
        )
        response = requests.get(pdf_conv_url)

        save_dir = os.path.join(PDF_SAVE_PATH, ticker, str(year), form_type)
        os.makedirs(save_dir, exist_ok=True)

        if response.status_code == 200:
            file_name = f"{ticker}_{form_type}_{year}.pdf"
            file_path = os.path.join(save_dir, file_name)

            with open(file_path, "wb") as pdf_file:
                pdf_file.write(response.content)

            self.stdout.write(
                self.style.SUCCESS(f"PDF downloaded successfully: {file_path}")
            )

            filing_date = datetime.strptime(filing_date[:10], "%Y-%m-%d").date()

            # Store metadata in the database
            sec_filing, created = SECFilings.objects.update_or_create(
                ticker=ticker,
                defaults={
                    "form_type": form_type,
                    "filing_date": filing_date,
                    "path_to_doc": file_path,
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Created new entry for {ticker} ({form_type}, {filing_date})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️ Updated existing entry for {ticker} ({form_type}, {filing_date})"
                    )
                )

        else:
            self.stderr.write(
                self.style.ERROR(
                    f"❌ Failed to download PDF for {ticker}. Status Code: {response.status_code}"
                )
            )
