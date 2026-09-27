# cs2-market-analyzer
cs2 deki itemlerin steam fiyatlarını kontrol edebileceğiniz , phyton ile pazar fiyatlarını çeken otomasyon 

## Kullanım

Python 3 ile scripti çalıştırın:

```bash
python /home/runner/work/cs2-market-analyzer/cs2-market-analyzer/cs2_market_prices.py "AK-47 | Redline (Field-Tested)" "AWP | Asiimov (Battle-Scarred)"
```

Dosyadan (her satırda bir item olacak şekilde):

```bash
python /home/runner/work/cs2-market-analyzer/cs2-market-analyzer/cs2_market_prices.py --file /path/to/items.txt
```

Opsiyonlar:
- `--currency`: Steam para birimi kodu (varsayılan `1`, USD)
- `--country`: Ülke kodu (varsayılan `US`)
