import sys
import os
from pprint import pprint

sys.path.append("/Users/suriyaprakash/Zhahi/Project/Linkedinbot")
from database import get_active_products

pprint(get_active_products())
