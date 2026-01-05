"""Constants and enums for the bot."""

from enum import Enum

# Pagination
ITEMS_PER_PAGE = 10


# Conversation states
class ConvState(int, Enum):
    SEARCH_BRAND = 1
    SEARCH_PRICE = 2
    SEARCH_RAM = 3
    SEARCH_SCREEN = 4
    RECOMMEND_USE_CASE = 10
    RECOMMEND_BUDGET = 11
    RECOMMEND_SCREEN = 12


# Filter options
TOP_BRANDS = ["Dell", "HP", "Lenovo", "Asus", "Acer", "Apple"]
PRICE_OPTIONS = [50000, 80000, 120000, 150000]  # Max price options
RAM_OPTIONS = [8, 16, 32]
SCREEN_OPTIONS = [13, 14, 15, 17]  # Min screen size options
USE_CASES = [
    "Programming",
    "Gaming",
    "Office",
    "Student",
    "Video Editing",
    "General Use",
]
