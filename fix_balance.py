from database import remove_balance
# The user got double credited by $25.00, so we remove $25.00
remove_balance(605114766, 25.0)
print("Balance fixed.")
