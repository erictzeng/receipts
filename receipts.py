from csv import DictReader

import click
import io
import requests
from tabulate import tabulate


RESERVED = ['Item', 'Description', 'Price', 'Tax?', '']
TAX = 1.0925

def resolve_prices(people, item, tax):
    star_value = compute_star_value(people, item)
    allocations = [parse_allocation(item[person], star_value)
                   for person in people]
    total_price = unallocated = parse_price(item, tax)
    prices = []
    for allocation in allocations:
        if not allocation:
            prices.append(0)
            continue
        price = round(allocation * total_price)
        if price > unallocated:
            price = unallocated
        unallocated -= price
        prices.append(price)
    if unallocated:
        prices[0] += unallocated
    return prices, allocations

def compute_star_value(people, item):
    allocated = 0.
    stars = 0
    for person in people:
        if not item[person]:
            continue
        elif item[person] == '*':
            stars += 1
            continue
        try:
            allocated += float(item[person])
            continue
        except ValueError:
            raise ValueError('Unexpected allocation: {}'
                             .format(repr(item[person])))
    if allocated >= 1:
        raise ValueError('{} is overallocated!'.format(item['Item']))
    return (1 - allocated) / stars if stars else float('inf')

def parse_price(item, tax):
    price = int(item['Price'].replace('$', '').replace('.', ''))
    if item['Tax?']:
        price = round(price * tax)
    return price

def parse_allocation(allocation, star_value):
    try:
        return float(allocation)
    except ValueError:
        if allocation == '*':
            return star_value
        else:
            return allocation

def fmt(price):
    dollars = price // 100
    cents = price % 100
    return '{}.{:02}'.format(dollars, cents)

@click.command()
@click.option('--csv', type=click.File('r'))
@click.option('--gsheet')
@click.option('--tax', type=float, default=9.25)
def main(csv, gsheet, tax):
    if csv is None and gsheet is None:
        print('No input specified.')
    if csv is not None and gsheet is not None:
        print('--csv and --gsheet are exclusive options.')
    if csv is not None:
        reader = DictReader(csv)
    elif gsheet is not None:
        r = requests.get('https://docs.google.com/spreadsheet/ccc?key={}&output=csv'.format(gsheet))
        r.raise_for_status()
        buf = io.StringIO(r.text)
        reader = DictReader(buf)
    if tax < 1:
        # tax is probably specified as fraction instead of percentage points
        tax += 1
    else:
        tax += 100
        tax /= 100
    people = [name for name in reader.fieldnames if name not in RESERVED]
    receipts = {name: [] for name in people}
    totals = {name: 0 for name in people}
    for item in reader:
        prices, allocations = resolve_prices(people, item, tax)
        for person, price, allocation in zip(people, prices, allocations):
            if price:
                totals[person] += price
                receipts[person].append((item['Description'], fmt(price), allocation))
    for person in people:
        print(person)
        receipts[person].append(('TOTAL', fmt(totals[person]), 1.0))
        print(tabulate(receipts[person], floatfmt=".2f"))
        print()
    print('Grand total:', fmt(sum(totals.values())))

if __name__ == '__main__':
    main()
