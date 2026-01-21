"""
LiraShield - Application Entry Point

Track your portfolio returns adjusted for inflation using CPI/USD benchmarks.
Protect your purchasing power with real return analytics.
"""

from core.database import init_db
from ui import create_ui

init_db()


def main():
    """Entry point for the application."""
    demo = create_ui()
    demo.launch()


if __name__ == "__main__":
    main()
