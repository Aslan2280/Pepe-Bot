import json
import os
import random
import logging
import asyncio
import re
import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8474641060:AAH4cRqRcBFhvEaQowd0jG8WQtPDTffzN0w"
ADMIN_ID = 6539341659
DATABASE_FILE = "casino_data.json"
PROMO_FILE = "promo_codes.json"
SHOP_FILE = "shop_items.json"
INVENTORY_FILE = "inventory.json"
COUNTERS_FILE = "counters.json"
MARKET_FILE = "market_listings.json"

START_BALANCE = 10000  # Стартовый баланс: 10к

logging.basicConfig(level=logging.INFO)

# === СОСТОЯНИЯ ===
class TransferStates(StatesGroup):
    select_item = State()
    enter_username = State()
    confirm = State()

class SellStates(StatesGroup):
    waiting_price = State()

# === БАЗА ДАННЫХ ===
class Database:
    def __init__(self, file):
        self.file = file
        self._ensure()
    
    def _ensure(self):
        """Создает файл, если его нет"""
        if not os.path.exists(self.file):
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def read(self):
        """Читает данные из файла"""
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def write(self, data):
        """Записывает данные в файл"""
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# === СЧЕТЧИКИ ===
class CountersDB:
    def __init__(self):
        self.db = Database(COUNTERS_FILE)
    
    def get_next_number(self, item_id):
        """Получить следующий глобальный номер для предмета"""
        data = self.db.read()
        if 'item_counters' not in data:
            data['item_counters'] = {}
        
        current = data['item_counters'].get(item_id, 0)
        next_num = current + 1
        data['item_counters'][item_id] = next_num
        self.db.write(data)
        return next_num
    
    def get_market_number(self):
        """Получить следующий номер для лота"""
        data = self.db.read()
        if 'market_counter' not in data:
            data['market_counter'] = 0
        
        next_num = data['market_counter'] + 1
        data['market_counter'] = next_num
        self.db.write(data)
        return next_num
    
    def get_all_counters(self):
        """Получить все счетчики"""
        data = self.db.read()
        return data.get('item_counters', {})

# === ПОЛЬЗОВАТЕЛИ (ИСПРАВЛЕНО) ===
class UserDB:
    def __init__(self):
        self.db = Database(DATABASE_FILE)
    
    def get(self, user_id):
        """Получить данные пользователя, создать если нет"""
        data = self.db.read()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            # Создаем нового пользователя и сразу сохраняем
            data[user_id_str] = {
                'balance': START_BALANCE,
                'games_played': 0,
                'wins': 0,
                'used_promocodes': []
            }
            self.db.write(data)
            return data[user_id_str]
        
        # Проверяем наличие всех ключей у существующего пользователя
        user = data[user_id_str]
        changed = False
        
        if 'balance' not in user:
            user['balance'] = START_BALANCE
            changed = True
        if 'games_played' not in user:
            user['games_played'] = 0
            changed = True
        if 'wins' not in user:
            user['wins'] = 0
            changed = True
        if 'used_promocodes' not in user:
            user['used_promocodes'] = []
            changed = True
        
        if changed:
            self.db.write(data)
        
        return user
    
    def update(self, user_id, **kwargs):
        """Обновить данные пользователя"""
        data = self.db.read()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = self.get(user_id)
        
        for k, v in kwargs.items():
            data[user_id_str][k] = v
        
        self.db.write(data)
    
    def top(self, limit=10):
        """Получить топ игроков (без админа)"""
        data = self.db.read()
        users = []
        for uid, u in data.items():
            if uid == str(ADMIN_ID):
                continue
            if 'balance' not in u:
                u['balance'] = 0
            users.append((uid, u))
        
        users.sort(key=lambda x: x[1].get('balance', 0), reverse=True)
        return users[:limit]
    
    def all_users(self):
        """Вернуть список всех ID пользователей"""
        return [int(uid) for uid in self.db.read().keys()]
    
    def get_all_users_data(self):
        """Вернуть все данные пользователей (для админа)"""
        return self.db.read()

# === ПРОМОКОДЫ (ИСПРАВЛЕНО) ===
class PromoDB:
    def __init__(self):
        self.db = Database(PROMO_FILE)
    
    def create(self, code, reward, limit=100, days=30):
        """Создать новый промокод"""
        promos = self.db.read()
        if code in promos:
            return False
        
        promos[code] = {
            'reward': reward,
            'limit': limit,
            'used': 0,
            'expires': (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(),
            'users': []
        }
        self.db.write(promos)
        return True
    
    def use(self, code, user_id, user_db):
        """Использовать промокод"""
        promos = self.db.read()
        if code not in promos:
            return {'ok': False, 'msg': '❌ Промокод не найден!'}
        
        p = promos[code]
        
        # Проверяем наличие всех ключей
        if 'expires' not in p:
            return {'ok': False, 'msg': '❌ Ошибка в промокоде!'}
        if 'limit' not in p:
            p['limit'] = 100
        if 'used' not in p:
            p['used'] = 0
        if 'users' not in p:
            p['users'] = []
        
        if datetime.datetime.now() > datetime.datetime.fromisoformat(p['expires']):
            return {'ok': False, 'msg': '❌ Промокод просрочен!'}
        if p['used'] >= p['limit']:
            return {'ok': False, 'msg': '❌ Лимит использований!'}
        if user_id in p['users']:
            return {'ok': False, 'msg': '❌ Вы уже использовали!'}
        
        user = user_db.get(user_id)
        new_balance = user['balance'] + p['reward']
        user['used_promocodes'].append(code)
        user_db.update(user_id, balance=new_balance, used_promocodes=user['used_promocodes'])
        
        p['used'] += 1
        p['users'].append(user_id)
        self.db.write(promos)
        
        return {'ok': True, 'msg': f'🎉 Получено: {self.fmt(p["reward"])}'}
    
    def all(self):
        """Получить все промокоды"""
        promos = self.db.read()
        # Проверяем каждый промокод
        for code, p in promos.items():
            if 'expires' not in p:
                p['expires'] = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
            if 'limit' not in p:
                p['limit'] = 100
            if 'used' not in p:
                p['used'] = 0
            if 'users' not in p:
                p['users'] = []
        return promos
    
    def fmt(self, n):
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}ккк"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}кк"
        if n >= 1000:
            return f"{n/1000:.1f}к"
        return str(n)

# === МАГАЗИН (ИСПРАВЛЕНО) ===
class ShopDB:
    def __init__(self):
        self.shop = Database(SHOP_FILE)
        self.inv = Database(INVENTORY_FILE)
        self.counters = CountersDB()
    
    def add(self, id, name, price, quantity, description="", emoji="🎁"):
        """Добавить товар в магазин"""
        items = self.shop.read()
        if id in items:
            return False
        
        items[id] = {
            'name': name, 
            'price': price, 
            'quantity': quantity,
            'sold': 0,
            'description': description,
            'emoji': emoji
        }
        self.shop.write(items)
        return True
    
    def buy(self, id, user_id, user_db):
        """Купить товар"""
        items = self.shop.read()
        inv = self.inv.read()
        
        if id not in items:
            return {'ok': False, 'msg': '❌ Товар не найден!'}
        
        item = items[id]
        user = user_db.get(user_id)
        
        if item['quantity'] <= 0:
            return {'ok': False, 'msg': '❌ Нет в наличии!'}
        if user['balance'] < item['price']:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        # Получаем следующий глобальный номер для этого типа NFT
        global_number = self.counters.get_next_number(id)
        
        new_balance = user['balance'] - item['price']
        user_db.update(user_id, balance=new_balance)
        
        item['quantity'] -= 1
        item['sold'] += 1
        self.shop.write(items)
        
        user_inv = inv.get(str(user_id), [])
        user_inv.append({
            'item_id': id,
            'global_number': global_number,
            'name': item['name'],
            'emoji': item['emoji'],
            'description': item['description'],
            'purchased_at': datetime.datetime.now().isoformat(),
            'unique_id': f"{user_id}_{id}_{len(user_inv)}_{random.randint(1000, 9999)}"
        })
        inv[str(user_id)] = user_inv
        self.inv.write(inv)
        
        return {
            'ok': True, 
            'msg': f'🎉 Куплено {item["emoji"]} {item["name"]} #{global_number}',
            'number': global_number
        }
    
    def items(self):
        """Получить все товары"""
        items = self.shop.read()
        # Проверяем каждый товар
        for id, item in items.items():
            if 'quantity' not in item:
                item['quantity'] = 0
            if 'sold' not in item:
                item['sold'] = 0
            if 'description' not in item:
                item['description'] = ''
            if 'emoji' not in item:
                item['emoji'] = '🎁'
        return items
    
    def inventory(self, user_id):
        """Получить инвентарь пользователя"""
        inv = self.inv.read()
        return inv.get(str(user_id), [])
    
    def get_item_by_unique_id(self, unique_id):
        """Найти предмет по unique_id во всех инвентарях"""
        inv = self.inv.read()
        for user_id, items in inv.items():
            for item in items:
                if item.get('unique_id') == unique_id:
                    return item, int(user_id)
        return None, None
    
    def remove_from_inventory(self, user_id, unique_id):
        """Удалить предмет из инвентаря"""
        inv = self.inv.read()
        if str(user_id) in inv:
            inv[str(user_id)] = [i for i in inv[str(user_id)] if i.get('unique_id') != unique_id]
            self.inv.write(inv)
            return True
        return False
    
    def add_to_inventory(self, user_id, item_data):
        """Добавить предмет в инвентарь"""
        inv = self.inv.read()
        if str(user_id) not in inv:
            inv[str(user_id)] = []
        inv[str(user_id)].append(item_data)
        self.inv.write(inv)

# === РЫНОК (ИСПРАВЛЕНО) ===
class MarketDB:
    def __init__(self):
        self.db = Database(MARKET_FILE)
        self.counters = CountersDB()
    
    def add_listing(self, seller_id, seller_name, item, price):
        """Создать новый лот"""
        listings = self.db.read()
        listing_number = self.counters.get_market_number()
        
        listing_id = f"listing_{listing_number}"
        listings[listing_id] = {
            'listing_number': listing_number,
            'item_id': item['item_id'],
            'global_number': item['global_number'],
            'unique_id': item['unique_id'],
            'seller_id': seller_id,
            'seller_name': seller_name,
            'name': item['name'],
            'emoji': item['emoji'],
            'description': item['description'],
            'price': price,
            'listed_at': datetime.datetime.now().isoformat(),
            'status': 'active'
        }
        self.db.write(listings)
        return listing_id, listing_number
    
    def get_listings(self):
        """Получить все активные лоты"""
        listings = self.db.read()
        return {k: v for k, v in listings.items() if v.get('status') == 'active'}
    
    def get_listing(self, listing_id):
        """Получить конкретный лот"""
        listings = self.db.read()
        return listings.get(listing_id)
    
    def buy_listing(self, listing_id, buyer_id, buyer_name, shop_db, user_db):
        """Купить лот"""
        listings = self.db.read()
        if listing_id not in listings:
            return {'ok': False, 'msg': '❌ Лот не найден!'}
        
        listing = listings[listing_id]
        if listing['status'] != 'active':
            return {'ok': False, 'msg': '❌ Этот лот уже продан!'}
        
        if listing['seller_id'] == buyer_id:
            return {'ok': False, 'msg': '❌ Нельзя купить свой лот!'}
        
        # Проверяем деньги покупателя
        buyer = user_db.get(buyer_id)
        if buyer['balance'] < listing['price']:
            return {'ok': False, 'msg': f'❌ Недостаточно средств! Нужно: {self.fmt(listing["price"])}'}
        
        # Проверяем, что предмет еще существует у продавца
        item, owner_id = shop_db.get_item_by_unique_id(listing['unique_id'])
        if not item or owner_id != listing['seller_id']:
            listings[listing_id]['status'] = 'error'
            self.db.write(listings)
            return {'ok': False, 'msg': '❌ Ошибка: предмет больше не доступен!'}
        
        # Списываем деньги у покупателя
        new_buyer_balance = buyer['balance'] - listing['price']
        user_db.update(buyer_id, balance=new_buyer_balance)
        
        # Начисляем деньги продавцу
        seller = user_db.get(listing['seller_id'])
        new_seller_balance = seller['balance'] + listing['price']
        user_db.update(listing['seller_id'], balance=new_seller_balance)
        
        # Удаляем предмет у продавца
        shop_db.remove_from_inventory(listing['seller_id'], listing['unique_id'])
        
        # Добавляем предмет покупателю (с тем же глобальным номером)
        shop_db.add_to_inventory(buyer_id, item)
        
        # Помечаем лот как проданный
        listings[listing_id]['status'] = 'sold'
        listings[listing_id]['buyer_id'] = buyer_id
        listings[listing_id]['buyer_name'] = buyer_name
        listings[listing_id]['sold_at'] = datetime.datetime.now().isoformat()
        self.db.write(listings)
        
        return {
            'ok': True,
            'msg': f'✅ Покупка успешна!',
            'item': item,
            'price': listing['price']
        }
    
    def cancel_listing(self, listing_id, user_id, shop_db):
        """Отменить продажу"""
        listings = self.db.read()
        if listing_id not in listings:
            return {'ok': False, 'msg': '❌ Лот не найден!'}
        
        listing = listings[listing_id]
        if listing['seller_id'] != user_id:
            return {'ok': False, 'msg': '❌ Это не ваш лот!'}
        
        if listing['status'] != 'active':
            return {'ok': False, 'msg': '❌ Этот лот уже не активен!'}
        
        # Проверяем, что предмет еще не был продан
        item, owner_id = shop_db.get_item_by_unique_id(listing['unique_id'])
        if not item:
            # Предмет пропал - просто удаляем лот
            listings[listing_id]['status'] = 'cancelled'
            self.db.write(listings)
            return {'ok': True, 'msg': '✅ Продажа отменена (предмет не найден)'}
        
        # Возвращаем предмет продавцу (он и так у него, если не продан)
        # Просто меняем статус лота
        listings[listing_id]['status'] = 'cancelled'
        self.db.write(listings)
        
        return {'ok': True, 'msg': '✅ Продажа отменена, предмет возвращен в инвентарь'}
    
    def get_user_listings(self, user_id):
        """Получить все лоты пользователя"""
        listings = self.db.read()
        return {k: v for k, v in listings.items() if v.get('seller_id') == user_id}
    
    def fmt(self, n):
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}ккк"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}кк"
        if n >= 1000:
            return f"{n/1000:.1f}к"
        return str(n)

# === ИГРЫ ===
class Games:
    def __init__(self, db):
        self.db = db
    
    def can(self, user_id, amount):
        user = self.db.get(user_id)
        return user['balance'] >= amount
    
    def coin(self, user_id, bet, choice):
        if not self.can(user_id, bet):
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        user = self.db.get(user_id)
        result = random.choice(['орел', 'решка'])
        win = choice == result
        
        if win:
            win_amount = bet * 2
            new_balance = user['balance'] + win_amount
            self.db.update(user_id, 
                          balance=new_balance, 
                          games_played=user.get('games_played', 0) + 1, 
                          wins=user.get('wins', 0) + 1)
            return {'ok': True, 'win': True, 'res': result, 'amount': win_amount, 'balance': new_balance}
        else:
            new_balance = user['balance'] - bet
            self.db.update(user_id, 
                          balance=new_balance, 
                          games_played=user.get('games_played', 0) + 1)
            return {'ok': True, 'win': False, 'res': result, 'amount': bet, 'balance': new_balance}
    
    def slots(self, user_id, bet):
        if not self.can(user_id, bet):
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        symbols = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
        reels = [random.choice(symbols) for _ in range(3)]
        user = self.db.get(user_id)
        
        if reels[0] == reels[1] == reels[2]:
            mult = 10 if reels[0] == '7️⃣' else 5
            win = bet * mult
            new_balance = user['balance'] + win
            self.db.update(user_id, 
                          balance=new_balance, 
                          games_played=user.get('games_played', 0) + 1, 
                          wins=user.get('wins', 0) + 1)
            return {'ok': True, 'win': True, 'reels': reels, 'mult': mult, 'amount': win, 'balance': new_balance}
        else:
            new_balance = user['balance'] - bet
            self.db.update(user_id, 
                          balance=new_balance, 
                          games_played=user.get('games_played', 0) + 1)
            return {'ok': True, 'win': False, 'reels': reels, 'amount': bet, 'balance': new_balance}
    
    def dice(self, user_id, bet, pred):
        if not self.can(user_id, bet):
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        if pred < 1 or pred > 6:
            return {'ok': False, 'msg': '❌ Число от 1 до 6!'}
        
        user = self.db.get(user_id)
        roll = random.randint(1, 6)
        win = pred == roll
        
        if win:
            win_amount = bet * 6
            new_balance = user['balance'] + win_amount
            self.db.update(user_id, 
                          balance=new_balance, 
                          games_played=user.get('games_played', 0) + 1, 
                          wins=user.get('wins', 0) + 1)
            return {'ok': True, 'win': True, 'roll': roll, 'amount': win_amount, 'balance': new_balance}
        else:
            new_balance = user['balance'] - bet
            self.db.update(user_id, 
                          balance=new_balance, 
                          games_played=user.get('games_played', 0) + 1)
            return {'ok': True, 'win': False, 'roll': roll, 'amount': bet, 'balance': new_balance}

# === ИГРА КРАШ ===
class CrashGame:
    def __init__(self, db):
        self.db = db
        self.active_games = {}  # user_id -> game_data
    
    def start(self, user_id, bet, target_x):
        """Начать игру Краш"""
        # Если есть активная игра, но она уже завершена - удаляем
        if user_id in self.active_games:
            if self.active_games[user_id].get('status') in ['won', 'lost']:
                del self.active_games[user_id]
            else:
                return {'ok': False, 'msg': '❌ У вас уже есть активная игра! Завершите её.'}
        
        user = self.db.get(user_id)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        if target_x < 1.1:
            return {'ok': False, 'msg': '❌ Минимальный множитель: 1.1x'}
        
        if target_x > 100:
            return {'ok': False, 'msg': '❌ Максимальный множитель: 100x'}
        
        # Списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Генерируем случайный множитель
        crash_point = self._generate_crash_point()
        
        game_data = {
            'user_id': user_id,
            'bet': bet,
            'target_x': target_x,
            'crash_point': crash_point,
            'status': 'active'
        }
        
        self.active_games[user_id] = game_data
        
        # Определяем результат
        if crash_point >= target_x:
            # Выигрыш
            win_amount = int(bet * target_x)
            final_balance = new_balance + win_amount
            self.db.update(user_id, 
                          balance=final_balance,
                          games_played=user.get('games_played', 0) + 1,
                          wins=user.get('wins', 0) + 1)
            game_data['status'] = 'won'
            game_data['win_amount'] = win_amount
            game_data['final_balance'] = final_balance
        else:
            # Проигрыш
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            game_data['status'] = 'lost'
            game_data['final_balance'] = new_balance
        
        # Удаляем игру после завершения
        if game_data['status'] in ['won', 'lost']:
            del self.active_games[user_id]
        
        return {
            'ok': True,
            'game_data': game_data
        }
    
    def _generate_crash_point(self):
        """Генерирует случайную точку краша"""
        r = random.random()
        crash = 1.0 / (1.0 - r * 0.95)  # Уменьшил множители
        return round(crash, 2)

# === МИНЫ С НОВЫМИ МНОЖИТЕЛЯМИ ===
class Mines:
    def __init__(self, db):
        self.db = db
        self.games = {}
    
    def get_multipliers(self, mines_count):
        """Возвращает множители в зависимости от количества мин"""
        if mines_count <= 3:  # 1-3 мины
            return {
                1: 1.01, 2: 1.05, 3: 1.10, 4: 1.15, 5: 1.21,
                6: 1.28, 7: 1.35, 8: 1.35, 9: 1.43, 10: 1.45,
                11: 1.52, 12: 1.62, 13: 1.73, 14: 1.87, 15: 1.95,
                16: 2.00, 17: 2.12, 18: 2.19, 19: 2.46, 20: 2.61,
                21: 3.03, 22: 3.57, 23: 4.21, 24: 5.00
            }
        elif mines_count <= 6:  # 4-6 мин
            return {
                1: 1.21, 2: 1.53, 3: 1.96, 4: 2.53, 5: 3.32,
                6: 4.41, 7: 6.67, 8: 8.42, 9: 10.45, 10: 15.52,
                11: 21.55, 12: 25.60, 13: 30.65, 14: 39.70, 15: 47.75,
                16: 67.80, 17: 71.85, 18: 79.90, 19: 84.95, 20: 87.00,
                21: 93.05, 22: 95.10, 23: 97.15, 24: 100.00
            }
        elif mines_count <= 10:  # 7-10 мин
            return {
                1: 1.43, 2: 2.15, 3: 3.20, 4: 5.25, 5: 6.30,
                6: 7.35, 7: 8.40, 8: 9.45, 9: 10.50, 10: 15.55,
                11: 23.60, 12: 25.65, 13: 31.70, 14: 38.75, 15: 41.80,
                16: 49.85, 17: 56.90, 18: 61.95, 19: 67.00, 20: 72.05,
                21: 89.10, 22: 95.15, 23: 99.20, 24: 100.00
            }
        else:  # 11+ мин
            return {
                1: 1.80, 2: 3.18, 3: 7.24, 4: 12.30, 5: 21.36,
                6: 26.42, 7: 32.48, 8: 37.54, 9: 45.60, 10: 49.66,
                11: 53.72, 12: 58.78, 13: 64.84, 14: 72.90, 15: 86.96,
                16: 93.02, 17: 97.08, 18: 100.14, 19: 112.20, 20: 126.26,
                21: 132.32, 22: 139.38, 23: 145.44, 24: 150.50
            }
    
    def start(self, user_id, bet, mines=3):
        if user_id in self.games:
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её.'}
        
        user = self.db.get(user_id)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        field = [['⬜']*5 for _ in range(5)]
        m_pos = []
        while len(m_pos) < mines:
            pos = (random.randint(0,4), random.randint(0,4))
            if pos not in m_pos:
                m_pos.append(pos)
        
        self.games[user_id] = {
            'bet': bet, 
            'field': field, 
            'mines': m_pos, 
            'count': mines,
            'opened': [], 
            'mult': 1.0, 
            'mults': self.get_multipliers(mines), 
            'won': 0
        }
        
        self.db.update(user_id, balance=user['balance'] - bet)
        return {'ok': True, 'data': self.games[user_id]}
    
    def open(self, user_id, row, col):
        if user_id not in self.games:
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[user_id]
        pos = (row, col)
        
        if pos in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто!'}
        
        if pos in g['mines']:
            for r,c in g['mines']:
                g['field'][r][c] = '💣'
            g['field'][row][col] = '💥'
            opened = len(g['opened'])
            del self.games[user_id]
            return {'ok': True, 'over': True, 'field': g['field'], 'opened': opened, 'bet': g['bet']}
        
        g['opened'].append(pos)
        g['field'][row][col] = '🟩'
        opened = len(g['opened'])
        g['mult'] = g['mults'].get(opened, 2.5)  # Максимум 2.5x
        g['won'] = int(g['bet'] * g['mult'])
        
        return {
            'ok': True, 
            'over': False, 
            'field': g['field'],
            'opened': opened, 
            'mult': g['mult'], 
            'won': g['won'],
            'max': 25 - g['count']
        }
    
    def cashout(self, user_id):
        if user_id not in self.games:
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[user_id]
        user = self.db.get(user_id)
        new_balance = user['balance'] + g['won']
        self.db.update(user_id, balance=new_balance, 
                      games_played=user.get('games_played', 0) + 1,
                      wins=user.get('wins', 0) + 1)
        
        for r,c in g['mines']:
            g['field'][r][c] = '💣'
        
        opened = len(g['opened'])
        mult = g['mult']
        bet = g['bet']
        won = g['won']
        field = [row[:] for row in g['field']]
        
        del self.games[user_id]
        return {
            'ok': True, 
            'won': won, 
            'balance': new_balance,
            'field': field, 
            'opened': opened, 
            'mult': mult, 
            'bet': bet
        }
    
    def kb(self, user_id, field, active=True):
        kb = []
        for i in range(5):
            row = []
            for j in range(5):
                if field[i][j] in ['🟩','💣','💥']:
                    row.append(InlineKeyboardButton(text=field[i][j], callback_data="ignore"))
                else:
                    emoji = "🟦" if active else "⬛"
                    row.append(InlineKeyboardButton(text=emoji, callback_data=f"mines_{user_id}_{i}_{j}"))
            kb.append(row)
        if active:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"cashout_{user_id}")])
        kb.append([InlineKeyboardButton(text="🎮 Новая", callback_data="mines_new")])
        return InlineKeyboardMarkup(inline_keyboard=kb)

# === ОСНОВНОЙ БОТ ===
class BotCore:
    def __init__(self):
        self.db = UserDB()
        self.promo = PromoDB()
        self.shop = ShopDB()
        self.market = MarketDB()
        self.games = Games(self.db)
        self.crash = CrashGame(self.db)
        self.mines = Mines(self.db)
        self.counters = CountersDB()
    
    def parse_bet(self, text, user_balance=None):
        """
        Парсит ставку с поддержкой:
        - числа: 1000
        - суффиксы: 1к, 2.5кк, 3ккк
        - ключевое слово "все" - весь баланс
        """
        if not text:
            return 0
        
        text = str(text).lower().strip()
        
        # Обработка "все" - весь баланс
        if text == 'все' and user_balance is not None:
            return user_balance
        
        # Обработка чисел с суффиксами
        match = re.match(r'^(\d+(?:\.\d+)?)(к+)$', text)
        if match:
            num = float(match.group(1))
            k = len(match.group(2))
            if k == 1:
                return int(num * 1000)
            elif k == 2:
                return int(num * 1_000_000)
            elif k == 3:
                return int(num * 1_000_000_000)
        
        # Обычное число
        try:
            return int(text)
        except:
            return 0
    
    def parse_float(self, text):
        """Парсит число с плавающей точкой"""
        try:
            return float(text.replace(',', '.'))
        except:
            return 0
    
    def fmt(self, n):
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}ккк"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}кк"
        if n >= 1000:
            return f"{n/1000:.1f}к"
        return str(n)

# === СОЗДАЕМ ЭКЗЕМПЛЯР ===
bot_core = BotCore()

# === ПРОВЕРКА НА ЛС ===
def is_private(message: Message):
    return message.chat.type == 'private'

# === КОМАНДА ПОМОЩЬ ===
async def cmd_help(msg: Message):
    """Показывает список всех команд"""
    help_text = """
🎮 **ВСЕ ИГРЫ БОТА**

**💰 ИГРЫ НА ДЕНЬГИ:**
• `монетка [ставка] [орел/решка]` - классическая монетка (x2)
• `слоты [ставка]` - игровые автоматы (x5 или x10)
• `кубик [ставка] [число]` - угадай число на кубике (x6)
• `краш [ставка] [иксы]` - ракета летит до множителя
• `мины [ставка] [мин]` - минное поле с множителями

**💰 ОСОБАЯ СТАВКА:**
• `все` - поставить ВЕСЬ баланс (например: `мины все 5`)

**📊 ПРОФИЛЬ И БАЛАНС:**
• `баланс` или `б` - проверить баланс
• `профиль` - полная статистика
• `п` - быстрый профиль (работает в группах)
• `топ` - топ игроков по балансу

**🛍️ NFT МАГАЗИН (только в ЛС):**
• `магазин` - посмотреть доступные NFT
• `инвентарь` - мои NFT
• `рынок` - купить NFT у других игроков
• `мои лоты` - мои объявления о продаже

**🔄 ПЕРЕВОДЫ:**
• `дать [сумма]` - перевести деньги (в ответ на сообщение)
• `передать [номер] [id]` - передать NFT

**🎫 ПРОМОКОДЫ:**
• `промо [код]` - активировать промокод

**💰 ФОРМАТЫ СТАВОК:**
• 1к = 1,000
• 1кк = 1,000,000
• 1ккк = 1,000,000,000
• `все` = весь баланс

**📝 ПРИМЕРЫ:**
• `монетка 1к орел`
• `краш 500 2.5`
• `мины все 5` - поставить всё на 5 мин
• `кубик все 6` - поставить всё на число 6

✨ **Баланс при старте: 10,000 коинов**
"""
    await msg.answer(help_text, parse_mode="Markdown")

# === ОБРАБОТЧИКИ КОМАНД ===
async def cmd_start(msg: Message):
    bot_core.db.get(msg.from_user.id)
    await msg.answer(
        f"🎰 Добро пожаловать, {msg.from_user.first_name}!\n"
        f"💰 Баланс: {bot_core.fmt(START_BALANCE)}\n\n"
        f"📝 Основные команды:\n"
        f"• `помощь` или `help` - все команды\n"
        f"• `баланс` / `б` - проверить баланс\n"
        f"• `профиль` / `п` - статистика\n"
        f"• `топ` - топ игроков\n"
        f"• `магазин` - NFT магазин (только ЛС)\n"
        f"• `инвентарь` - мои NFT (только ЛС)\n\n"
        f"🎮 Игры:\n"
        f"• `монетка 1к орел`\n"
        f"• `слоты 500`\n"
        f"• `кубик 1кк 5`\n"
        f"• `краш 1000 2.5`\n"
        f"• `мины все 5` - поставить ВСЁ!\n\n"
        f"💰 1к=1,000 | 1кк=1,000,000 | 1ккк=1,000,000,000",
        parse_mode="Markdown"
    )

async def cmd_balance(msg: Message):
    user = bot_core.db.get(msg.from_user.id)
    await msg.answer(f"💰 Баланс: {bot_core.fmt(user['balance'])}")

async def cmd_short_profile(msg: Message):
    """Короткий профиль (команда 'п') - работает везде"""
    user = bot_core.db.get(msg.from_user.id)
    inv = bot_core.shop.inventory(msg.from_user.id)
    games = user.get('games_played', 0)
    wins = user.get('wins', 0)
    rate = (wins/games*100) if games > 0 else 0
    
    # Сортируем NFT по глобальному номеру
    sorted_inv = sorted(inv, key=lambda x: x.get('global_number', 0))
    
    text = f"📊 Профиль {msg.from_user.first_name}\n"
    text += f"💰 {bot_core.fmt(user['balance'])}\n"
    text += f"🎮 {games} игр | 🏆 {wins} побед | {rate:.1f}%\n\n"
    text += f"🎒 NFT ({len(inv)}):\n"
    
    for item in sorted_inv[:5]:  # показываем первые 5
        text += f"#{item.get('global_number', '?')} {item['emoji']} {item['name']}\n"
    
    if len(inv) > 5:
        text += f"...и еще {len(inv)-5}\n"
    
    await msg.answer(text)

async def cmd_full_profile(msg: Message):
    """Полный профиль (команда 'профиль')"""
    user = bot_core.db.get(msg.from_user.id)
    inv = bot_core.shop.inventory(msg.from_user.id)
    games = user.get('games_played', 0)
    wins = user.get('wins', 0)
    rate = (wins/games*100) if games > 0 else 0
    
    # Сортируем NFT по глобальному номеру
    sorted_inv = sorted(inv, key=lambda x: x.get('global_number', 0))
    
    text = f"📊 ПОДРОБНЫЙ ПРОФИЛЬ {msg.from_user.first_name}\n"
    text += f"💰 Баланс: {bot_core.fmt(user['balance'])}\n"
    text += f"🎮 Всего игр: {games}\n"
    text += f"🏆 Побед: {wins}\n"
    text += f"📈 Процент побед: {rate:.1f}%\n"
    text += f"🎫 Использовано промокодов: {len(user.get('used_promocodes', []))}\n\n"
    text += f"🎒 КОЛЛЕКЦИЯ NFT ({len(inv)}):\n"
    
    # Группируем по типу для красивого отображения
    by_type = {}
    for item in sorted_inv:
        key = f"{item['item_id']} {item['emoji']} {item['name']}"
        if key not in by_type:
            by_type[key] = []
        by_type[key].append(item['global_number'])
    
    for item_key, numbers in by_type.items():
        numbers_str = ', '.join([f"#{n}" for n in sorted(numbers)])
        text += f"• {item_key}: {numbers_str}\n"
    
    await msg.answer(text)

async def cmd_top(msg: Message):
    top = bot_core.db.top()
    if not top:
        await msg.answer("📊 Рейтинг пуст")
        return
    text = "🏆 ТОП ИГРОКОВ:\n"
    for i, (uid, u) in enumerate(top, 1):
        text += f"{i}. ID {uid} - {bot_core.fmt(u.get('balance', 0))}\n"
    await msg.answer(text)

async def cmd_shop(msg: Message):
    # Проверяем, что команда вызвана в личке
    if not is_private(msg):
        await msg.answer("❌ Магазин доступен только в личных сообщениях с ботом!\nПерейдите в ЛС: @dropGGbot")
        return
    
    items = bot_core.shop.items()
    if not items:
        await msg.answer("🛍️ Магазин пуст")
        return
    kb = []
    for id, item in items.items():
        if item.get('quantity', 0) > 0:
            kb.append([InlineKeyboardButton(
                text=f"{item.get('emoji', '🎁')} {item.get('name', 'Товар')} | {bot_core.fmt(item.get('price', 0))}",
                callback_data=f"shop_view_{id}"
            )])
    kb.append([InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="shop_my_inv")])
    await msg.answer("🛍️ МАГАЗИН:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_inventory(msg: Message):
    # Проверяем, что команда вызвана в личке
    if not is_private(msg):
        await msg.answer("❌ Инвентарь доступен только в личных сообщениях с ботом!\nПерейдите в ЛС: @dropGGbot")
        return
    
    inv = bot_core.shop.inventory(msg.from_user.id)
    if not inv:
        await msg.answer("🎒 Инвентарь пуст")
        return
    
    # Сортируем по глобальному номеру
    sorted_inv = sorted(inv, key=lambda x: x.get('global_number', 0))
    
    kb = []
    for item in sorted_inv:
        global_num = item.get('global_number', 0)
        kb.append([InlineKeyboardButton(
            text=f"#{global_num} {item.get('emoji', '🎁')} {item.get('name', 'Предмет')}",
            callback_data=f"inv_view_{item.get('unique_id')}"
        )])
    
    kb.append([InlineKeyboardButton(text="🏪 На рынок", callback_data="goto_market")])
    await msg.answer("🎒 ВАШ ИНВЕНТАРЬ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_market(msg: Message):
    # Проверяем, что команда вызвана в личке
    if not is_private(msg):
        await msg.answer("❌ Рынок доступен только в личных сообщениях с ботом!\nПерейдите в ЛС: @dropGGbot")
        return
    
    listings = bot_core.market.get_listings()
    if not listings:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="shop_my_inv")]
        ])
        await msg.answer("🏪 РЫНОК\n\nНа данный момент нет активных лотов", reply_markup=kb)
        return
    
    kb = []
    for lid, lot in listings.items():
        kb.append([InlineKeyboardButton(
            text=f"{lot['emoji']} {lot['item_id']} #{lot['global_number']} | {bot_core.fmt(lot['price'])}",
            callback_data=f"market_view_{lid}"
        )])
    
    kb.append([InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="shop_my_inv")])
    kb.append([InlineKeyboardButton(text="📋 Мои лоты", callback_data="my_listings")])
    
    await msg.answer(f"🏪 РЫНОК ({len(listings)} лотов):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_my_listings(msg: Message):
    # Проверяем, что команда вызвана в личке
    if not is_private(msg):
        await msg.answer("❌ Эта команда доступна только в личных сообщениях с ботом!")
        return
    
    listings = bot_core.market.get_user_listings(msg.from_user.id)
    active = {k: v for k, v in listings.items() if v.get('status') == 'active'}
    
    if not active:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏪 На рынок", callback_data="goto_market")],
            [InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="shop_my_inv")]
        ])
        await msg.answer("📋 У вас нет активных лотов", reply_markup=kb)
        return
    
    kb = []
    for lid, lot in active.items():
        kb.append([InlineKeyboardButton(
            text=f"{lot['emoji']} {lot['item_id']} #{lot['global_number']} | {bot_core.fmt(lot['price'])}",
            callback_data=f"my_listing_view_{lid}"
        )])
    
    kb.append([InlineKeyboardButton(text="🏪 На рынок", callback_data="goto_market")])
    kb.append([InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="shop_my_inv")])
    
    await msg.answer(f"📋 ВАШИ ЛОТЫ ({len(active)}):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_give(msg: Message):
    """Обрабатывает команду 'дать' для перевода денег через ответ на сообщение"""
    if not msg.reply_to_message:
        await msg.answer("❌ Эта команда работает только как ответ на сообщение пользователя!\n"
                        "Нажмите на сообщение человека и выберите 'Ответить', затем напишите 'дать 1000'")
        return
    
    recipient_id = msg.reply_to_message.from_user.id
    sender_id = msg.from_user.id
    
    if sender_id == recipient_id:
        await msg.answer("❌ Нельзя переводить деньги самому себе!")
        return
    
    text = msg.text.strip().lower()
    parts = text.split()
    
    if len(parts) != 2 or parts[0] not in ['дать', 'дай']:
        await msg.answer("❌ Неверный формат. Используйте: дать [сумма]\n"
                        "Пример: дать 10к")
        return
    
    # Получаем баланс отправителя для обработки "все"
    sender = bot_core.db.get(sender_id)
    amount = bot_core.parse_bet(parts[1], sender['balance'])
    
    if amount <= 0:
        await msg.answer("❌ Неверная сумма перевода!")
        return
    
    if sender['balance'] < amount:
        await msg.answer(f"❌ Недостаточно средств! Ваш баланс: {bot_core.fmt(sender['balance'])}")
        return
    
    recipient = bot_core.db.get(recipient_id)
    
    new_sender_balance = sender['balance'] - amount
    new_recipient_balance = recipient['balance'] + amount
    
    bot_core.db.update(sender_id, balance=new_sender_balance)
    bot_core.db.update(recipient_id, balance=new_recipient_balance)
    
    await msg.answer(f"✅ Перевод выполнен!\n"
                    f"➖ Вы отправили: {bot_core.fmt(amount)}\n"
                    f"➕ Получатель: {msg.reply_to_message.from_user.full_name}\n"
                    f"💰 Ваш новый баланс: {bot_core.fmt(new_sender_balance)}")
    
    try:
        await msg.bot.send_message(
            recipient_id,
            f"🎁 Вам перевели {bot_core.fmt(amount)}!\n"
            f"📤 Отправитель: {msg.from_user.full_name}\n"
            f"💰 Ваш новый баланс: {bot_core.fmt(new_recipient_balance)}"
        )
    except:
        pass

async def cmd_promo(msg: Message, command: CommandObject):
    if not command.args:
        await msg.answer("Использование: промо КОД")
        return
    code = command.args.upper().strip()
    res = bot_core.promo.use(code, msg.from_user.id, bot_core.db)
    await msg.answer(res['msg'])

async def cmd_transfer(msg: Message, command: CommandObject):
    """Передача NFT по unique_id через команду"""
    # Проверяем, что команда вызвана в личке
    if not is_private(msg):
        await msg.answer("❌ Передача NFT доступна только в личных сообщениях с ботом!")
        return
    
    args = command.args.split() if command.args else []
    
    if len(args) != 2:
        # Показываем инструкцию
        inv = bot_core.shop.inventory(msg.from_user.id)
        if not inv:
            await msg.answer("🎒 Ваш инвентарь пуст")
            return
        
        text = "🔄 ПЕРЕДАЧА NFT\n\n"
        text += "Ваши NFT:\n"
        for i, item in enumerate(inv, 1):
            text += f"{i}. #{item.get('global_number', '?')} {item['emoji']} {item['name']}\n"
        text += "\nИспользуйте: /transfer [номер_в_списке] [id_получателя]\n"
        text += "Или выберите NFT в инвентаре и нажмите 'Передать'"
        await msg.answer(text)
        return
    
    try:
        # Пробуем найти NFT по номеру в списке
        idx = int(args[0]) - 1
        recipient_id = int(args[1])
        
        inv = bot_core.shop.inventory(msg.from_user.id)
        if idx < 0 or idx >= len(inv):
            await msg.answer("❌ Неверный номер NFT!")
            return
        
        item = inv[idx]
        unique_id = item['unique_id']
        
        # Проверяем, что предмет существует
        item_data, owner_id = bot_core.shop.get_item_by_unique_id(unique_id)
        if not item_data or owner_id != msg.from_user.id:
            await msg.answer("❌ Предмет не найден в вашем инвентаре!")
            return
        
        if recipient_id == msg.from_user.id:
            await msg.answer("❌ Нельзя передать предмет самому себе!")
            return
        
        # Удаляем у отправителя
        bot_core.shop.remove_from_inventory(msg.from_user.id, unique_id)
        
        # Добавляем получателю (с тем же глобальным номером)
        bot_core.shop.add_to_inventory(recipient_id, item_data)
        
        await msg.answer(
            f"✅ NFT передан!\n\n"
            f"#{item_data['global_number']} {item_data['emoji']} {item_data['name']}\n"
            f"📤 Получатель: ID {recipient_id}"
        )
        
        # Уведомляем получателя
        try:
            await msg.bot.send_message(
                recipient_id,
                f"🎁 Вам передали NFT!\n\n"
                f"#{item_data['global_number']} {item_data['emoji']} {item_data['name']}\n"
                f"📤 Отправитель: {msg.from_user.full_name}"
            )
        except:
            pass
            
    except ValueError:
        await msg.answer("❌ Неверный формат. Используйте: /transfer [номер] [id]")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

# === ИГРЫ ===
async def cmd_coin(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    # Получаем баланс пользователя для обработки "все"
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) == 2:
        bet = bot_core.parse_bet(args[0], balance)
        choice = args[1].lower().replace('ё', 'е')
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        if choice not in ['орел', 'решка']:
            await msg.answer("❌ Неверный выбор. Выберите 'орел' или 'решка'")
            return
        res = bot_core.games.coin(msg.from_user.id, bet, choice)
        if not res['ok']:
            await msg.answer(res['msg'])
            return
        if res['win']:
            await msg.answer(f"🎉 Выпал {res['res']}! +{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
        else:
            await msg.answer(f"😞 Выпал {res['res']}! -{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
    elif len(args) == 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🦅 Орел", callback_data=f"coin_{bet}_орел")],
            [InlineKeyboardButton(text="🪙 Решка", callback_data=f"coin_{bet}_решка")]
        ])
        await msg.answer(f"💰 Ставка: {bot_core.fmt(bet)}\nВыберите сторону:", reply_markup=kb)
    else:
        await msg.answer("Использование: монетка СТАВКА [орел/решка]\nПример: монетка 1кк орел")

async def cmd_slots(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    # Получаем баланс пользователя для обработки "все"
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) >= 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        res = bot_core.games.slots(msg.from_user.id, bet)
        if not res['ok']:
            await msg.answer(res['msg'])
            return
        reels = ' | '.join(res['reels'])
        if res['win']:
            await msg.answer(f"🎰 {reels}\n🎉 ДЖЕКПОТ x{res['mult']}! +{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
        else:
            await msg.answer(f"🎰 {reels}\n😞 Проигрыш: -{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
    else:
        await msg.answer("Использование: слоты СТАВКА\nПример: слоты 1кк")

async def cmd_dice(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    # Получаем баланс пользователя для обработки "все"
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) == 2:
        bet = bot_core.parse_bet(args[0], balance)
        pred = int(args[1])
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        if pred < 1 or pred > 6:
            await msg.answer("❌ Число должно быть от 1 до 6!")
            return
        res = bot_core.games.dice(msg.from_user.id, bet, pred)
        if not res['ok']:
            await msg.answer(res['msg'])
            return
        if res['win']:
            await msg.answer(f"🎲 Выпало {res['roll']}! +{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
        else:
            await msg.answer(f"🎲 Выпало {res['roll']}! -{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
    elif len(args) == 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(1,4)],
            [InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(4,7)]
        ])
        await msg.answer(f"💰 Ставка: {bot_core.fmt(bet)}\nВыберите число:", reply_markup=kb)
    else:
        await msg.answer("Использование: кубик СТАВКА ЧИСЛО\nПример: кубик 1кк 5")

async def cmd_crash(msg: Message, command: CommandObject):
    """Новая игра КРАШ"""
    args = command.args.split() if command.args else []
    
    # Получаем баланс пользователя для обработки "все"
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) == 2:
        bet = bot_core.parse_bet(args[0], balance)
        target_x = bot_core.parse_float(args[1])
        
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        
        if target_x < 1.1:
            await msg.answer("❌ Минимальный множитель: 1.1x")
            return
        
        if target_x > 100:
            await msg.answer("❌ Максимальный множитель: 100x")
            return
        
        # Запускаем игру
        res = bot_core.crash.start(msg.from_user.id, bet, target_x)
        
        if not res['ok']:
            await msg.answer(res['msg'])
            return
        
        game = res['game_data']
        crash = game['crash_point']
        
        if game['status'] == 'won':
            await msg.answer(
                f"🚀 КРАШ! Ракета улетела на x{crash}!\n\n"
                f"✅ Ваш множитель x{target_x} достигнут!\n"
                f"💰 Выигрыш: +{bot_core.fmt(game['win_amount'])}\n"
                f"💵 Новый баланс: {bot_core.fmt(game['final_balance'])}"
            )
        else:
            await msg.answer(
                f"💥 КРАШ! Ракета улетела на x{crash}...\n\n"
                f"❌ Вы не успели забрать (цель была x{target_x})\n"
                f"💸 Проигрыш: -{bot_core.fmt(bet)}\n"
                f"💵 Баланс: {bot_core.fmt(game['final_balance'])}"
            )
    
    elif len(args) == 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        
        # Предлагаем выбрать множитель
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1.5x", callback_data=f"crash_{bet}_1.5"),
             InlineKeyboardButton(text="2x", callback_data=f"crash_{bet}_2"),
             InlineKeyboardButton(text="3x", callback_data=f"crash_{bet}_3")],
            [InlineKeyboardButton(text="5x", callback_data=f"crash_{bet}_5"),
             InlineKeyboardButton(text="10x", callback_data=f"crash_{bet}_10"),
             InlineKeyboardButton(text="20x", callback_data=f"crash_{bet}_20")]
        ])
        await msg.answer(
            f"🚀 КРАШ\n\n"
            f"💰 Ставка: {bot_core.fmt(bet)}\n"
            f"Выберите множитель:",
            reply_markup=kb
        )
    
    else:
        await msg.answer(
            "🚀 ИГРА КРАШ\n\n"
            "Правила:\n"
            "• Выбираете ставку и множитель\n"
            "• Ракета взлетает со случайным множителем\n"
            "• Если множитель >= вашему - выигрыш\n"
            "• Если множитель < вашему - проигрыш\n\n"
            "Использование: краш СТАВКА [иксы]\n"
            "Пример: краш 1кк 2\n"
            "Пример: краш 500к 5.5\n"
            "Пример: краш все 2 - поставить всё!"
        )

async def cmd_mines(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    # Получаем баланс пользователя для обработки "все"
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) >= 1:
        bet = bot_core.parse_bet(args[0], balance)
        mines = int(args[1]) if len(args) > 1 else 3
        if bet <= 0 or bet > balance:
            await msg.answer(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        if mines < 1 or mines > 24:
            await msg.answer("❌ Количество мин должно быть от 1 до 24!")
            return
        res = bot_core.mines.start(msg.from_user.id, bet, mines)
        if not res['ok']:
            await msg.answer(res['msg'])
            return
        kb = bot_core.mines.kb(msg.from_user.id, res['data']['field'])
        await msg.answer(
            f"🎮 Мины | 💣 {mines}\n"
            f"💰 Ставка: {bot_core.fmt(bet)}\n"
            f"📈 x1.0 | 💎 0",
            reply_markup=kb
        )
    else:
        await msg.answer(
            "🎮 МИНЫ\n"
            "Правила: открывайте клетки, множитель растёт\n"
            "💣 мина - проигрыш\n\n"
            "Использование: мины СТАВКА [МИН]\n"
            "Пример: мины 1кк 5\n"
            "Пример: мины все 10 - поставить всё на 10 мин"
        )

# === CALLBACK ===
async def callback_handler(cb: CallbackQuery, state: FSMContext):
    data = cb.data
    
    if data.startswith('coin_'):
        parts = data.split('_')
        if len(parts) == 3:
            try:
                bet = int(parts[1])
                choice = parts[2]
                res = bot_core.games.coin(cb.from_user.id, bet, choice)
                if res['ok']:
                    if res['win']:
                        await cb.message.edit_text(f"🎉 Выпал {res['res']}! +{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
                    else:
                        await cb.message.edit_text(f"😞 Выпал {res['res']}! -{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
            except:
                await cb.answer("❌ Ошибка")
    
    elif data.startswith('dice_'):
        parts = data.split('_')
        if len(parts) == 3:
            try:
                bet = int(parts[1])
                pred = int(parts[2])
                res = bot_core.games.dice(cb.from_user.id, bet, pred)
                if res['ok']:
                    if res['win']:
                        await cb.message.edit_text(f"🎲 Выпало {res['roll']}! +{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
                    else:
                        await cb.message.edit_text(f"🎲 Выпало {res['roll']}! -{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
            except:
                await cb.answer("❌ Ошибка")
    
    elif data.startswith('crash_'):
        parts = data.split('_')
        if len(parts) == 3:
            try:
                bet = int(parts[1])
                target_x = float(parts[2])
                
                res = bot_core.crash.start(cb.from_user.id, bet, target_x)
                
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                
                game = res['game_data']
                crash = game['crash_point']
                
                if game['status'] == 'won':
                    await cb.message.edit_text(
                        f"🚀 КРАШ! Ракета улетела на x{crash}!\n\n"
                        f"✅ Ваш множитель x{target_x} достигнут!\n"
                        f"💰 Выигрыш: +{bot_core.fmt(game['win_amount'])}\n"
                        f"💵 Новый баланс: {bot_core.fmt(game['final_balance'])}"
                    )
                else:
                    await cb.message.edit_text(
                        f"💥 КРАШ! Ракета улетела на x{crash}...\n\n"
                        f"❌ Вы не успели забрать (цель была x{target_x})\n"
                        f"💸 Проигрыш: -{bot_core.fmt(bet)}\n"
                        f"💵 Баланс: {bot_core.fmt(game['final_balance'])}"
                    )
            except Exception as e:
                await cb.answer(f"❌ Ошибка: {e}")
    
    elif data.startswith('mines_'):
        parts = data.split('_')
        if len(parts) >= 4:
            try:
                user_id = int(parts[1])
                if cb.from_user.id != user_id:
                    await cb.answer("❌ Это не ваша игра!", show_alert=True)
                    return
                row = int(parts[2])
                col = int(parts[3])
                res = bot_core.mines.open(user_id, row, col)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                if res.get('over'):
                    kb = bot_core.mines.kb(user_id, res['field'], False)
                    await cb.message.edit_text(
                        f"💥 БУМ! Проигрыш: {bot_core.fmt(res['bet'])}\n"
                        f"🎯 Открыто: {res['opened']}",
                        reply_markup=kb
                    )
                else:
                    kb = bot_core.mines.kb(user_id, res['field'])
                    game = bot_core.mines.games.get(user_id)
                    if game:
                        await cb.message.edit_text(
                            f"🎮 Мины | 💣 {game['count']}\n"
                            f"💰 Ставка: {bot_core.fmt(game['bet'])}\n"
                            f"🎯 {res['opened']}/{res['max']} | 📈 x{res['mult']:.2f}\n"
                            f"💎 {bot_core.fmt(res['won'])}",
                            reply_markup=kb
                        )
            except Exception as e:
                await cb.answer(f"❌ Ошибка: {e}")
    
    elif data.startswith('cashout_'):
        parts = data.split('_')
        if len(parts) == 2:
            try:
                user_id = int(parts[1])
                if cb.from_user.id != user_id:
                    await cb.answer("❌ Это не ваша игра!", show_alert=True)
                    return
                res = bot_core.mines.cashout(user_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                kb = bot_core.mines.kb(user_id, res['field'], False)
                await cb.message.edit_text(
                    f"🏆 Выигрыш: +{bot_core.fmt(res['won'])}\n"
                    f"🎯 {res['opened']} | 📈 x{res['mult']:.2f}\n"
                    f"💰 Баланс: {bot_core.fmt(res['balance'])}",
                    reply_markup=kb
                )
            except:
                await cb.answer("❌ Ошибка")
    
    elif data == "mines_new":
        await cb.message.edit_text("🎮 Используй: мины СТАВКА [МИН]")
    
    # === МАГАЗИН ===
    elif data.startswith('shop_view_'):
        id = data[10:]
        items = bot_core.shop.items()
        if id not in items:
            await cb.answer("❌ Товар не найден", show_alert=True)
            return
        item = items[id]
        user = bot_core.db.get(cb.from_user.id)
        kb = []
        if item.get('quantity', 0) > 0 and user['balance'] >= item.get('price', 0):
            kb.append([InlineKeyboardButton(text="💳 Купить", callback_data=f"shop_buy_{id}")])
        kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="shop_back")])
        await cb.message.edit_text(
            f"{item.get('emoji', '🎁')} {item.get('name', 'Товар')}\n"
            f"📝 {item.get('description', '')}\n"
            f"💰 {bot_core.fmt(item.get('price', 0))}\n"
            f"📦 {item.get('quantity', 0)} шт | 📊 {item.get('sold', 0)} продано\n"
            f"💳 Ваш баланс: {bot_core.fmt(user['balance'])}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    
    elif data.startswith('shop_buy_'):
        id = data[9:]
        res = bot_core.shop.buy(id, cb.from_user.id, bot_core.db)
        await cb.answer(res['msg'], show_alert=True)
        if res['ok']:
            await cmd_shop(cb.message)
    
    elif data == "shop_my_inv":
        await cmd_inventory(cb.message)
    
    elif data == "shop_back":
        await cmd_shop(cb.message)
    
    # === ИНВЕНТАРЬ ===
    elif data.startswith('inv_view_'):
        unique_id = data[9:]
        inv = bot_core.shop.inventory(cb.from_user.id)
        item = None
        for i in inv:
            if i.get('unique_id') == unique_id:
                item = i
                break
        
        if not item:
            await cb.answer("❌ Предмет не найден", show_alert=True)
            return
        
        kb = [
            [InlineKeyboardButton(text="💰 Продать на рынке", callback_data=f"sell_{unique_id}")],
            [InlineKeyboardButton(text="🔄 Передать", callback_data=f"transfer_{unique_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="inv_back")]
        ]
        
        await cb.message.edit_text(
            f"#{item.get('global_number', '?')} {item['emoji']} {item['name']}\n\n"
            f"📝 {item.get('description', 'Нет описания')}\n"
            f"📅 Куплен: {item.get('purchased_at', '???')[:10]}\n"
            f"🔢 Уникальный ID: {item['unique_id']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    
    elif data == "inv_back":
        await cmd_inventory(cb.message)
    
    # === ПРОДАЖА ===
    elif data.startswith('sell_'):
        unique_id = data[5:]
        await state.update_data(sell_unique_id=unique_id)
        await state.set_state(SellStates.waiting_price)
        await cb.message.edit_text(
            "💰 Введите цену продажи:\n"
            "Пример: 50000, 1кк, 2.5кк\n\n"
            "❌ Для отмены отправьте /cancel"
        )
    
    # === ПЕРЕДАЧА ===
    elif data.startswith('transfer_'):
        unique_id = data[9:]
        await state.update_data(transfer_unique_id=unique_id)
        await state.set_state(TransferStates.enter_username)
        await cb.message.edit_text(
            "🔄 Введите ID получателя:\n"
            "Пример: 123456789\n\n"
            "❌ Для отмены отправьте /cancel"
        )
    
    # === РЫНОК ===
    elif data.startswith('market_view_'):
        lid = data[12:]
        lot = bot_core.market.get_listing(lid)
        if not lot or lot.get('status') != 'active':
            await cb.answer("❌ Лот не найден или уже продан", show_alert=True)
            return
        
        kb = [
            [InlineKeyboardButton(text="💳 Купить", callback_data=f"market_buy_{lid}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")]
        ]
        
        await cb.message.edit_text(
            f"Лот #{lot['listing_number']}: {lot['emoji']} {lot['item_id']} #{lot['global_number']}\n\n"
            f"📝 {lot.get('description', 'Нет описания')}\n"
            f"💰 Цена: {bot_core.fmt(lot['price'])}\n"
            f"👤 Продавец: {lot.get('seller_name', 'ID ' + str(lot['seller_id']))}\n"
            f"📅 Выставлен: {lot.get('listed_at', '???')[:10]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    
    elif data.startswith('market_buy_'):
        lid = data[11:]
        lot = bot_core.market.get_listing(lid)
        if not lot or lot.get('status') != 'active':
            await cb.answer("❌ Лот не найден или уже продан", show_alert=True)
            return
        
        res = bot_core.market.buy_listing(
            lid, 
            cb.from_user.id, 
            cb.from_user.full_name,
            bot_core.shop, 
            bot_core.db
        )
        
        await cb.answer(res['msg'], show_alert=True)
        if res['ok']:
            await cmd_market(cb.message)
    
    elif data == "market_back":
        await cmd_market(cb.message)
    
    elif data.startswith('my_listing_view_'):
        lid = data[16:]
        lot = bot_core.market.get_listing(lid)
        if not lot:
            await cb.answer("❌ Лот не найден", show_alert=True)
            return
        
        kb = [
            [InlineKeyboardButton(text="❌ Отменить продажу", callback_data=f"cancel_listing_{lid}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="my_listings_back")]
        ]
        
        await cb.message.edit_text(
            f"🏪 ВАШ ЛОТ #{lot['listing_number']}\n\n"
            f"{lot['emoji']} {lot['item_id']} #{lot['global_number']}\n"
            f"💰 Цена: {bot_core.fmt(lot['price'])}\n"
            f"📅 Выставлен: {lot.get('listed_at', '???')[:10]}\n"
            f"📊 Статус: {lot['status']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    
    elif data.startswith('cancel_listing_'):
        lid = data[15:]
        res = bot_core.market.cancel_listing(lid, cb.from_user.id, bot_core.shop)
        await cb.answer(res['msg'], show_alert=True)
        if res['ok']:
            await cmd_my_listings(cb.message)
    
    elif data == "my_listings_back":
        await cmd_my_listings(cb.message)
    
    elif data == "goto_market":
        await cmd_market(cb.message)
    
    elif data == "ignore":
        pass
    
    await cb.answer()

# === FSM ОБРАБОТЧИКИ ===
async def handle_sell_price(msg: Message, state: FSMContext):
    """Обработка ввода цены для продажи"""
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.answer("❌ Продажа отменена")
        return
    
    data = await state.get_data()
    unique_id = data.get('sell_unique_id')
    
    if not unique_id:
        await state.clear()
        await msg.answer("❌ Ошибка, попробуйте снова")
        return
    
    price = bot_core.parse_bet(msg.text)
    
    if price <= 0:
        await msg.answer("❌ Неверная цена! Введите число больше 0")
        return
    
    # Получаем предмет из инвентаря
    item, owner_id = bot_core.shop.get_item_by_unique_id(unique_id)
    
    if not item or owner_id != msg.from_user.id:
        await state.clear()
        await msg.answer("❌ Предмет не найден в вашем инвентаре")
        return
    
    # Создаем лот
    listing_id, listing_number = bot_core.market.add_listing(
        msg.from_user.id,
        msg.from_user.full_name,
        item,
        price
    )
    
    # Удаляем предмет из инвентаря
    bot_core.shop.remove_from_inventory(msg.from_user.id, unique_id)
    
    await state.clear()
    await msg.answer(
        f"✅ Предмет выставлен на продажу!\n\n"
        f"#{item['global_number']} {item['emoji']} {item['name']}\n"
        f"💰 Цена: {bot_core.fmt(price)}\n"
        f"📋 Номер лота: {listing_number}\n\n"
        f"Посмотреть лот: /market"
    )

async def handle_transfer_id(msg: Message, state: FSMContext):
    """Обработка ввода ID для передачи"""
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.answer("❌ Передача отменена")
        return
    
    data = await state.get_data()
    unique_id = data.get('transfer_unique_id')
    
    if not unique_id:
        await state.clear()
        await msg.answer("❌ Ошибка, попробуйте снова")
        return
    
    try:
        recipient_id = int(msg.text.strip())
    except:
        await msg.answer("❌ Неверный ID! Введите число")
        return
    
    if recipient_id == msg.from_user.id:
        await msg.answer("❌ Нельзя передать предмет самому себе!")
        return
    
    # Получаем предмет из инвентаря
    item, owner_id = bot_core.shop.get_item_by_unique_id(unique_id)
    
    if not item or owner_id != msg.from_user.id:
        await state.clear()
        await msg.answer("❌ Предмет не найден в вашем инвентаре")
        return
    
    # Удаляем у отправителя
    bot_core.shop.remove_from_inventory(msg.from_user.id, unique_id)
    
    # Добавляем получателю
    bot_core.shop.add_to_inventory(recipient_id, item)
    
    await state.clear()
    await msg.answer(
        f"✅ Предмет передан!\n\n"
        f"#{item['global_number']} {item['emoji']} {item['name']}\n"
        f"📤 Получатель: ID {recipient_id}"
    )
    
    # Уведомляем получателя
    try:
        await msg.bot.send_message(
            recipient_id,
            f"🎁 Вам передали NFT!\n\n"
            f"#{item['global_number']} {item['emoji']} {item['name']}\n"
            f"📤 Отправитель: {msg.from_user.full_name}"
        )
    except:
        pass

# === РУССКИЕ КОМАНДЫ ===
async def handle_russian(msg: Message, state: FSMContext):
    text = msg.text.lower().strip()
    
    if text in ['баланс', 'б']:
        await cmd_balance(msg)
    elif text in ['профиль', 'проф']:
        await cmd_full_profile(msg)
    elif text == 'п':
        await cmd_short_profile(msg)
    elif text == 'топ':
        await cmd_top(msg)
    elif text in ['помощь', 'help', 'команды']:
        await cmd_help(msg)
    elif text == 'магазин':
        await cmd_shop(msg)
    elif text in ['инвентарь', 'мои нфт']:
        await cmd_inventory(msg)
    elif text in ['рынок', 'маркет']:
        await cmd_market(msg)
    elif text == 'мои лоты':
        await cmd_my_listings(msg)
    elif text.startswith('промо '):
        code = text[6:].strip().upper()
        res = bot_core.promo.use(code, msg.from_user.id, bot_core.db)
        await msg.answer(res['msg'])
    elif text.startswith('дать ') or text.startswith('дай '):
        await cmd_give(msg)
    elif text.startswith('краш'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_crash(msg, FakeCommand(args))
        else:
            await cmd_crash(msg, FakeCommand(None))
    elif text.startswith('монетка'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_coin(msg, FakeCommand(args))
        else:
            await cmd_coin(msg, FakeCommand(None))
    elif text.startswith('слоты'):
        parts = text.split()
        if len(parts) >= 2:
            class FakeCommand:
                def __init__(self, args):
                    self.args = parts[1]
            await cmd_slots(msg, FakeCommand(parts[1]))
        else:
            await cmd_slots(msg, FakeCommand(None))
    elif text.startswith('кубик'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_dice(msg, FakeCommand(args))
        else:
            await cmd_dice(msg, FakeCommand(None))
    elif text.startswith('мины'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_mines(msg, FakeCommand(args))
        else:
            await cmd_mines(msg, FakeCommand(None))

# === АДМИН ===
async def admin_promo_list(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    promos = bot_core.promo.all()
    if not promos:
        await msg.answer("📭 Нет промокодов")
        return
    text = "📋 ПРОМОКОДЫ:\n"
    for code, p in promos.items():
        try:
            days = (datetime.datetime.fromisoformat(p['expires']) - datetime.datetime.now()).days
            text += f"\n🎫 {code}\n💰 {bot_core.fmt(p['reward'])} | 🎯 {p['used']}/{p['limit']}\n⏰ {days} дн.\n"
        except:
            text += f"\n🎫 {code} (ошибка в данных)\n"
    await msg.answer(text)

async def admin_shop_list(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    items = bot_core.shop.items()
    if not items:
        await msg.answer("🛍️ Магазин пуст")
        return
    text = "🛍️ ТОВАРЫ:\n"
    for id, item in items.items():
        text += f"\n{item.get('emoji', '🎁')} {item.get('name', 'Товар')} (ID: {id})\n"
        text += f"💰 {bot_core.fmt(item.get('price', 0))} | 📦 {item.get('quantity', 0)} | 📊 {item.get('sold', 0)}\n"
    await msg.answer(text)

async def admin_counters(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    counters = bot_core.counters.get_all_counters()
    text = "📊 СЧЕТЧИКИ NFT:\n"
    for item_id, count in counters.items():
        text += f"• {item_id}: {count} экземпляров\n"
    await msg.answer(text)

async def admin_users_list(msg: Message):
    """Админ-команда для просмотра всех пользователей"""
    if msg.from_user.id != ADMIN_ID:
        return
    
    data = bot_core.db.get_all_users_data()
    total_users = len(data)
    
    # Подсчет активных пользователей (с балансом > START_BALANCE или игравших)
    active_users = 0
    for uid, user in data.items():
        if user.get('games_played', 0) > 0 or user.get('balance', 0) > START_BALANCE:
            active_users += 1
    
    text = f"📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ:\n"
    text += f"👥 Всего в базе: {total_users}\n"
    text += f"🎮 Активных: {active_users}\n"
    text += f"💤 Неактивных: {total_users - active_users}\n\n"
    text += f"📋 Список ID (первые 20):\n"
    
    for i, uid in enumerate(sorted(data.keys())[:20]):
        user = data[uid]
        text += f"{i+1}. {uid}: {bot_core.fmt(user.get('balance', 0))} | 🎮 {user.get('games_played', 0)}\n"
    
    if len(data) > 20:
        text += f"...и еще {len(data) - 20}\n"
    
    await msg.answer(text)

# === ЗАПУСК ===
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Команды со слэшем
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_balance, Command("balance"))
    dp.message.register(cmd_full_profile, Command("profile"))
    dp.message.register(cmd_short_profile, Command("p"))
    dp.message.register(cmd_top, Command("top"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_shop, Command("shop"))
    dp.message.register(cmd_inventory, Command("inventory"))
    dp.message.register(cmd_market, Command("market"))
    dp.message.register(cmd_my_listings, Command("my_listings"))
    dp.message.register(cmd_promo, Command("promo"))
    dp.message.register(cmd_transfer, Command("transfer"))
    dp.message.register(cmd_coin, Command("coinflip"))
    dp.message.register(cmd_slots, Command("slots"))
    dp.message.register(cmd_dice, Command("dice"))
    dp.message.register(cmd_crash, Command("crash"))
    dp.message.register(cmd_mines, Command("mines"))
    
    # Новая команда "дать"
    dp.message.register(cmd_give, Command("give"))
    
    # Админ команды
    dp.message.register(admin_promo_list, Command("admin_promo_list"))
    dp.message.register(admin_shop_list, Command("admin_shop_list"))
    dp.message.register(admin_counters, Command("admin_counters"))
    dp.message.register(admin_users_list, Command("admin_users"))
    
    # FSM обработчики
    dp.message.register(handle_sell_price, SellStates.waiting_price)
    dp.message.register(handle_transfer_id, TransferStates.enter_username)
    
    # Русские команды
    dp.message.register(handle_russian, F.text)
    
    # Callback
    dp.callback_query.register(callback_handler)
    
    print("✅ Бот запущен!")
    print(f"✅ Новый токен: {BOT_TOKEN[:10]}...")
    print(f"✅ Стартовый баланс: {START_BALANCE} коинов")
    print("✅ Новая игра: КРАШ")
    print("✅ Новые множители в минах (сбалансированные)")
    print("✅ Ставка 'все' - поставить весь баланс")
    print("✅ Глобальная нумерация NFT")
    print("✅ Рынок с лотами")
    print("✅ Команда 'помощь' для всех команд")
    print("✅ Админ-команда /admin_users для просмотра всех пользователей")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Бот остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
