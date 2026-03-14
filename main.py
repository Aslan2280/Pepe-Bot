import json
import os
import random
import logging
import asyncio
import re
import datetime
import string
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "8474641060:AAH4cRqRcBFhvEaQowd0jG8WQtPDTffzN0w"
CREATOR_ID = 6539341659
DATABASE_FILE = "casino_data.json"
PROMO_FILE = "promo_codes.json"
SHOP_FILE = "shop_items.json"
INVENTORY_FILE = "inventory.json"
COUNTERS_FILE = "counters.json"
STATUS_SHOP_FILE = "status_shop.json"
BANK_DATA_FILE = "bank_data.json"
BANK_SETTINGS_FILE = "bank_settings.json"
MARKET_FILE = "market.json"
BANNED_USERS_FILE = "banned_users.json"
ADMINS_FILE = "admins.json"
ADMIN_LOGS_FILE = "admin_logs.json"
EVENTS_FILE = "events.json"
ADS_FILE = "ads_tasks.json"
USER_TASKS_FILE = "user_tasks.json"
START_BALANCE = 10000

MIN_PROMO_REWARD = 1000
MAX_PROMO_REWARD = 10000000
MIN_PROMO_LIMIT = 1
MAX_PROMO_LIMIT = 50
PROMO_DAYS_VALID = 7
PROMO_CODE_LENGTH = 8

logging.basicConfig(level=logging.INFO)

class TransferStates(StatesGroup):
    enter_username = State()
    confirm = State()

class TransferNFTStates(StatesGroup):
    waiting_user = State()
    waiting_nft = State()
    waiting_confirm = State()

class BankStates(StatesGroup):
    waiting_deposit_amount = State()
    waiting_deposit_days = State()
    waiting_loan_amount = State()
    waiting_loan_days = State()
    waiting_card_amount = State()
    waiting_loan_payment = State()

class PromoStates(StatesGroup):
    waiting_reward = State()
    waiting_limit = State()

class MarketStates(StatesGroup):
    waiting_price = State()

class AdminStates(StatesGroup):
    waiting_nft_id = State()
    waiting_nft_name = State()
    waiting_nft_price = State()
    waiting_nft_quantity = State()
    waiting_nft_description = State()
    waiting_nft_emoji = State()
    waiting_status_name = State()
    waiting_ban_reason = State()

class KNBTicTacToe(StatesGroup):
    waiting_choice = State()
    duel_waiting_opponent = State()
    duel_creator_choice = State()
    duel_opponent_choice = State()

class PyramidDoors(StatesGroup):
    waiting_doors = State()

class AdStates(StatesGroup):
    waiting_channel = State()
    waiting_subscribers = State()
    waiting_reward = State()
    waiting_confirm = State()

class DB:
    def __init__(self, file):
        self.file = file
        self._ensure()
    def _ensure(self):
        if not os.path.exists(self.file):
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    def read(self):
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    def write(self, data):
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

class CountersDB:
    def __init__(self):
        self.db = DB(COUNTERS_FILE)
    def get_next(self, item_id):
        data = self.db.read()
        data.setdefault('item_counters', {})
        data['item_counters'][item_id] = data['item_counters'].get(item_id, 0) + 1
        self.db.write(data)
        return data['item_counters'][item_id]

class BanDB:
    def __init__(self):
        self.db = DB(BANNED_USERS_FILE)
    
    def is_banned(self, uid):
        data = self.db.read()
        return str(uid) in data
    
    def ban(self, uid, admin_id, reason=""):
        data = self.db.read()
        uid = str(uid)
        data[uid] = {
            'banned_at': datetime.datetime.now().isoformat(),
            'banned_by': admin_id,
            'reason': reason if reason else "Не указана"
        }
        self.db.write(data)
        return True
    
    def unban(self, uid):
        data = self.db.read()
        uid = str(uid)
        if uid in data:
            del data[uid]
            self.db.write(data)
            return True
        return False
    
    def get_ban_info(self, uid):
        data = self.db.read()
        return data.get(str(uid))

class AdminDB:
    def __init__(self):
        self.db = DB(ADMINS_FILE)
        self._ensure_creator()
    
    def _ensure_creator(self):
        data = self.db.read()
        if str(CREATOR_ID) not in data:
            data[str(CREATOR_ID)] = {
                "is_creator": True,
                "added_by": None,
                "added_at": datetime.datetime.now().isoformat()
            }
            self.db.write(data)
    
    def is_admin(self, uid):
        data = self.db.read()
        return str(uid) in data
    
    def is_creator(self, uid):
        data = self.db.read()
        admin = data.get(str(uid))
        return admin and admin.get("is_creator", False)
    
    def get_all_admins(self):
        return self.db.read()
    
    def add_admin(self, uid, added_by):
        if self.is_admin(uid):
            return {'ok': False, 'msg': '❌ Уже админ'}
        
        data = self.db.read()
        data[str(uid)] = {
            "is_creator": False,
            "added_by": added_by,
            "added_at": datetime.datetime.now().isoformat()
        }
        self.db.write(data)
        return {'ok': True, 'msg': f'✅ {uid} назначен админом'}
    
    def remove_admin(self, uid, removed_by):
        if not self.is_admin(uid):
            return {'ok': False, 'msg': '❌ Не админ'}
        
        if self.is_creator(uid):
            return {'ok': False, 'msg': '❌ Нельзя удалить создателя'}
        
        data = self.db.read()
        del data[str(uid)]
        self.db.write(data)
        return {'ok': True, 'msg': f'✅ {uid} снят с админки'}
    
    def get_admin_info(self, uid):
        return self.db.read().get(str(uid))

class AdminLogs:
    def __init__(self):
        self.db = DB(ADMIN_LOGS_FILE)
        self._ensure()
    
    def _ensure(self):
        data = self.db.read()
        if not data or "logs" not in data:
            data = {"logs": []}
            self.db.write(data)
    
    def add_log(self, admin_id, action, target_id=None, amount=None, details=""):
        data = self.db.read()
        
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "admin_id": admin_id,
            "action": action,
            "target_id": target_id,
            "amount": amount,
            "details": details
        }
        
        data["logs"].append(log_entry)
        self.db.write(data)
        return log_entry
    
    def get_logs(self, limit=50, admin_id=None, action=None):
        data = self.db.read()
        logs = data.get("logs", [])
        
        if admin_id:
            logs = [log for log in logs if log.get("admin_id") == admin_id]
        if action:
            logs = [log for log in logs if log.get("action") == action]
        
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return logs[:limit]
    
    def clear_logs(self):
        data = {"logs": []}
        self.db.write(data)
        return True
    
    def get_stats(self):
        data = self.db.read()
        logs = data.get("logs", [])
        
        stats = {
            "total_actions": len(logs),
            "by_action": {},
            "by_admin": {},
            "total_given": 0,
            "total_taken": 0,
            "total_bans": 0,
            "last_24h": 0
        }
        
        now = datetime.datetime.now()
        day_ago = now - datetime.timedelta(days=1)
        
        for log in logs:
            action = log.get("action", "unknown")
            admin = str(log.get("admin_id", "unknown"))
            amount = log.get("amount", 0) or 0
            
            stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
            stats["by_admin"][admin] = stats["by_admin"].get(admin, 0) + 1
            
            if action == "give":
                stats["total_given"] += amount
            elif action == "take":
                stats["total_taken"] += amount
            elif action == "ban":
                stats["total_bans"] += 1
            
            try:
                log_time = datetime.datetime.fromisoformat(log.get("timestamp", ""))
                if log_time > day_ago:
                    stats["last_24h"] += 1
            except:
                pass
        
        return stats
    
    def format_logs(self, logs, detailed=False):
        if not logs:
            return "📭 Логов нет"
        
        text = "📋 Логи админов\n\n"
        
        for log in logs[:10]:
            timestamp = log.get("timestamp", "Unknown")[:16].replace("T", " ")
            admin_id = log.get("admin_id", "?")
            action = log.get("action", "?")
            target = log.get("target_id", "—")
            amount = log.get("amount")
            details = log.get("details", "")
            
            action_emoji = {
                "give": "💰", "take": "💸", "ban": "⛔", "unban": "✅",
                "make_admin": "👑", "remove_admin": "👤", "create_promo": "🎫",
                "give_status": "⭐", "create_nft": "🖼️", "clear_logs": "🧹",
                "give_bank": "💳", "take_bank": "💳", "event_start": "🎉",
                "event_end": "⏰", "toggle_status": "⚙️", "create_ad": "📢"
            }.get(action, "🔹")
            
            amount_str = f" | {fmt(amount)}" if amount else ""
            target_str = f" | {target}" if target != "—" else ""
            details_str = f"\n  {details}" if details else ""
            
            text += f"{action_emoji} {action}{amount_str}{target_str}\n"
            text += f"  {timestamp} | {admin_id}{details_str}\n\n"
        
        if detailed and len(logs) > 10:
            text += f"... и еще {len(logs) - 10}"
        
        return text

class UserDB:
    def __init__(self):
        self.db = DB(DATABASE_FILE)
    
    def get(self, uid):
        data = self.db.read()
        uid = str(uid)
        if uid not in data:
            data[uid] = {'balance': START_BALANCE, 'games_played': 0, 'wins': 0,
                        'used_promocodes': [], 'created_promocodes': [], 'status': 'novice',
                        'last_bonus': None, 'bonus_history': []}
            self.db.write(data)
            return data[uid]
        return data[uid]
    
    def update(self, uid, **kwargs):
        data = self.db.read()
        uid = str(uid)
        if uid not in data:
            data[uid] = self.get(uid)
        data[uid].update(kwargs)
        self.db.write(data)
    
    def top(self, limit=10):
        data = self.db.read()
        users = []
        for uid, u in data.items():
            if is_admin(int(uid)):
                continue
            users.append((uid, u))
        return sorted(users, key=lambda x: x[1].get('balance', 0), reverse=True)[:limit]
    
    def top_by_status(self):
        data = self.db.read()
        status_groups = {}
        for uid, u in data.items():
            if is_admin(int(uid)):
                continue
            status = u.get('status', 'novice')
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append((uid, u))
        
        for status in status_groups:
            status_groups[status].sort(key=lambda x: x[1].get('balance', 0), reverse=True)
        return status_groups
    
    def get_total_balance(self, uid):
        """Возвращает общий баланс пользователя (наличные + карта)"""
        user = self.get(uid)
        bank_data = core.bank.get(uid)
        return user['balance'] + bank_data['card_balance']
    
    def get_all_users_total_balance(self):
        """Возвращает список всех пользователей с их общим балансом"""
        data = self.db.read()
        result = []
        for uid, user in data.items():
            # Пропускаем админов, если нужно
            # if is_admin(int(uid)):
            #     continue
            
            bank_data = core.bank.get(uid)
            total = user['balance'] + bank_data['card_balance']
            result.append((uid, total, user['balance'], bank_data['card_balance']))
        
        return sorted(result, key=lambda x: x[1], reverse=True)

class StatusShop:
    def __init__(self):
        self.db = DB(STATUS_SHOP_FILE)
        if not self.db.read():
            self.db.write({
                "novice": {
                    "name": "Новичок",
                    "emoji": "🌱",
                    "price": 0,
                    "min_bonus": 500,
                    "max_bonus": 2500,
                    "description": "Начальный статус",
                    "sell": True
                },
                "player": {
                    "name": "Игрок",
                    "emoji": "🎮",
                    "price": 50000,
                    "min_bonus": 2500,
                    "max_bonus": 10000,
                    "description": "Обычный игрок",
                    "sell": True
                },
                "gambler": {
                    "name": "Азартный",
                    "emoji": "🎲",
                    "price": 250000,
                    "min_bonus": 10000,
                    "max_bonus": 50000,
                    "description": "Любит риск",
                    "sell": True
                },
                "vip": {
                    "name": "VIP",
                    "emoji": "💎",
                    "price": 1000000,
                    "min_bonus": 50000,
                    "max_bonus": 250000,
                    "description": "VIP клиент",
                    "sell": True
                },
                "legend": {
                    "name": "Легенда",
                    "emoji": "👑",
                    "price": 5000000,
                    "min_bonus": 250000,
                    "max_bonus": 1000000,
                    "description": "Легенда казино",
                    "sell": True
                },
                "oligarch": {
                    "name": "Олигарх",
                    "emoji": "💰",
                    "price": 25000000,
                    "min_bonus": 1000000,
                    "max_bonus": 5000000,
                    "description": "Олигарх",
                    "sell": True
                },
                "immortal": {
                    "name": "Бессмертный",
                    "emoji": "⚡",
                    "price": 100000000,
                    "min_bonus": 5000000,
                    "max_bonus": 25000000,
                    "description": "Бессмертный",
                    "sell": True
                }
            })
    
    def all(self):
        return self.db.read()
    
    def get_status(self, status_id):
        return self.db.read().get(status_id)
    
    def get_status_by_name(self, name):
        """Находит статус по названию (без учёта регистра)"""
        statuses = self.all()
        name_lower = name.lower().strip()
        
        # Сначала ищем точное совпадение
        for status_id, status in statuses.items():
            if status['name'].lower() == name_lower:
                return status_id, status
        
        # Если точного нет, ищем частичное
        for status_id, status in statuses.items():
            if name_lower in status['name'].lower():
                return status_id, status
        
        return None, None
    
    def buy(self, uid, status_id, user_db):
        statuses = self.all()
        if status_id not in statuses:
            return {'ok': False, 'msg': '❌ Статус не найден'}
        
        s = statuses[status_id]
        
        if not s.get('sell', True):
            return {'ok': False, 'msg': '❌ Не продаётся'}
        
        user = user_db.get(uid)
        if user['status'] == status_id:
            return {'ok': False, 'msg': '❌ Уже есть'}
        
        if user['balance'] < s['price']:
            return {'ok': False, 'msg': f'❌ Нужно {fmt(s["price"])}'}
        
        user_db.update(uid, balance=user['balance'] - s['price'], status=status_id)
        return {'ok': True, 'msg': f'✅ Куплен {s["emoji"]} {s["name"]}'}
    
    def admin_give_status(self, uid, status_id, user_db):
        statuses = self.all()
        if status_id not in statuses:
            return {'ok': False, 'msg': '❌ Статус не найден'}
        s = statuses[status_id]
        user = user_db.get(uid)
        user_db.update(uid, status=status_id)
        return {'ok': True, 'msg': f'✅ Выдан {s["emoji"]} {s["name"]}'}
    
    def get_bonus(self, uid, user_db):
        user = user_db.get(uid)
        statuses = self.all()
        status = statuses.get(user['status'], statuses['novice'])
        
        last_bonus = user.get('last_bonus')
        if last_bonus:
            try:
                last_time = datetime.datetime.fromisoformat(last_bonus)
                hours_passed = (datetime.datetime.now() - last_time).total_seconds() / 3600
                if hours_passed < 1:
                    next_bonus = int((1 - hours_passed) * 60)
                    return {'ok': False, 'msg': f'⏰ Через {next_bonus} мин'}
            except:
                pass
        
        bonus = random.randint(status['min_bonus'], status['max_bonus'])
        new_balance = user['balance'] + bonus
        
        user['last_bonus'] = datetime.datetime.now().isoformat()
        user['bonus_history'] = user.get('bonus_history', []) + [{'amount': bonus, 'time': datetime.datetime.now().isoformat()}]
        user_db.update(uid, balance=new_balance, last_bonus=user['last_bonus'], bonus_history=user['bonus_history'])
        
        return {
            'ok': True,
            'msg': f'✅Получено +{fmt(bonus)}\n💰Новый баланс {fmt(new_balance)}'
        }

class PromoDB:
    def __init__(self):
        self.db = DB(PROMO_FILE)
    
    def gen_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(PROMO_CODE_LENGTH))
            if code not in self.db.read():
                return code
    
    def create(self, reward, creator_id, limit=10):
        if reward < MIN_PROMO_REWARD:
            return {'ok': False, 'msg': f'❌ Мин {fmt(MIN_PROMO_REWARD)}'}
        if reward > MAX_PROMO_REWARD:
            return {'ok': False, 'msg': f'❌ Макс {fmt(MAX_PROMO_REWARD)}'}
        if limit < MIN_PROMO_LIMIT:
            return {'ok': False, 'msg': f'❌ Мин лимит {MIN_PROMO_LIMIT}'}
        if limit > MAX_PROMO_LIMIT:
            return {'ok': False, 'msg': f'❌ Макс лимит {MAX_PROMO_LIMIT}'}
        
        code = self.gen_code()
        promos = self.db.read()
        promos[code] = {
            'reward': reward, 'limit': limit, 'used': 0,
            'expires': (datetime.datetime.now() + datetime.timedelta(days=PROMO_DAYS_VALID)).isoformat(),
            'users': [], 'creator': creator_id, 'created_at': datetime.datetime.now().isoformat()
        }
        self.db.write(promos)
        return {'ok': True, 'code': code}
    
    def use(self, code, uid, user_db):
        promos = self.db.read()
        if code not in promos:
            return {'ok': False, 'msg': '❌ Не найден'}
        p = promos[code]
        if p.get('creator') == uid:
            return {'ok': False, 'msg': '❌ Свой нельзя'}
        if datetime.datetime.now() > datetime.datetime.fromisoformat(p['expires']):
            return {'ok': False, 'msg': '❌ Просрочен'}
        if p['used'] >= p['limit']:
            return {'ok': False, 'msg': '❌ Лимит исчерпан'}
        if uid in p['users']:
            return {'ok': False, 'msg': '❌ Уже использован'}
        
        user = user_db.get(uid)
        user_db.update(uid, balance=user['balance'] + p['reward'], used_promocodes=user['used_promocodes'] + [code])
        p['used'] += 1
        p['users'].append(uid)
        self.db.write(promos)
        return {'ok': True, 'msg': f'✅ +{fmt(p["reward"])}'}
    
    def my_promos(self, creator_id):
        promos = self.db.read()
        result = []
        total_used = total_claimed = 0
        for code, p in promos.items():
            if p.get('creator') == creator_id:
                p['code'] = code
                p['remaining'] = p['limit'] - p['used']
                p['claimed'] = p['used'] * p['reward']
                total_used += p['used']
                total_claimed += p['claimed']
                result.append(p)
        return result, total_used, total_claimed

class ShopDB:
    def __init__(self):
        self.shop = DB(SHOP_FILE)
        self.inv = DB(INVENTORY_FILE)
        self.counters = CountersDB()
    
    def add(self, id, name, price, qty, desc="", emoji="🎁"):
        items = self.shop.read()
        if id in items:
            return False
        items[id] = {'name': name, 'price': price, 'quantity': qty, 'sold': 0, 'description': desc, 'emoji': emoji}
        self.shop.write(items)
        return True
    
    def buy(self, id, uid, user_db):
        items = self.shop.read()
        if id not in items:
            return {'ok': False, 'msg': '❌ Не найден'}
        item = items[id]
        user = user_db.get(uid)
        if item['quantity'] <= 0:
            return {'ok': False, 'msg': '❌ Нет в наличии'}
        if user['balance'] < item['price']:
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        num = self.counters.get_next(id)
        user_db.update(uid, balance=user['balance'] - item['price'])
        item['quantity'] -= 1
        item['sold'] += 1
        self.shop.write(items)
        
        inv = self.inv.read()
        inv.setdefault(str(uid), []).append({
            'item_id': id, 'global_number': num, 'name': item['name'], 'emoji': item['emoji'],
            'description': item['description'], 'purchased_at': datetime.datetime.now().isoformat(),
            'unique_id': f"{uid}_{id}_{num}_{random.randint(1000,9999)}",
            'is_upgraded': False
        })
        self.inv.write(inv)
        return {'ok': True, 'msg': f'✅ {item["emoji"]} {item["name"]} #{num}'}
    
    def items(self):
        return self.shop.read()
    
    def inventory(self, uid):
        return self.inv.read().get(str(uid), [])
    
    def transfer_nft(self, from_uid, to_uid, unique_id):
        inv_data = self.inv.read()
        from_inv = inv_data.get(str(from_uid), [])
        to_inv = inv_data.get(str(to_uid), [])
        
        nft_index = None
        nft = None
        for i, item in enumerate(from_inv):
            if item['unique_id'] == unique_id:
                nft_index = i
                nft = item.copy()
                break
        
        if nft_index is None:
            return {'ok': False, 'msg': '❌ NFT не найден'}
        
        from_inv.pop(nft_index)
        nft['unique_id'] = f"{to_uid}_{nft['item_id']}_{nft.get('global_number', 0)}_{random.randint(1000,9999)}"
        nft['purchased_at'] = datetime.datetime.now().isoformat()
        nft['transferred_at'] = datetime.datetime.now().isoformat()
        to_inv.append(nft)
        
        inv_data[str(from_uid)] = from_inv
        inv_data[str(to_uid)] = to_inv
        self.inv.write(inv_data)
        
        return {'ok': True, 'msg': f'✅ NFT передан', 'nft': nft}

class Market:
    def __init__(self):
        self.db = DB(MARKET_FILE)
        self._ensure()
    
    def _ensure(self):
        data = self.db.read()
        if not data or 'market_counter' not in data:
            data = {
                "market_counter": 0,
                "listings": []
            }
            self.db.write(data)
    
    def get_next_id(self):
        data = self.db.read()
        current = data.get("market_counter", 0)
        new_id = current + 1
        data["market_counter"] = new_id
        self.db.write(data)
        return new_id
    
    def add_listing(self, seller_id, nft, price):
        if price <= 0:
            return {'ok': False, 'msg': '❌ Цена > 0'}
        
        listing_id = self.get_next_id()
        data = self.db.read()
        
        inv_data = core.shop.inv.read()
        seller_inv = inv_data.get(str(seller_id), [])
        
        found = False
        for i, item in enumerate(seller_inv):
            if item['unique_id'] == nft['unique_id']:
                seller_inv.pop(i)
                found = True
                break
        
        if not found:
            return {'ok': False, 'msg': '❌ NFT не найден'}
        
        inv_data[str(seller_id)] = seller_inv
        core.shop.inv.write(inv_data)
        
        listing_nft = nft.copy()
        listing_nft.pop('unique_id', None)
        
        listing = {
            'id': listing_id,
            'seller_id': seller_id,
            'nft': listing_nft,
            'price': price,
            'listed_at': datetime.datetime.now().isoformat(),
            'status': 'active'
        }
        
        data['listings'].append(listing)
        self.db.write(data)
        
        return {'ok': True, 'msg': f'✅ Выставлен за {fmt(price)}', 'listing_id': listing_id}
    
    def get_listings(self, page=0, per_page=5):
        data = self.db.read()
        active_listings = [l for l in data['listings'] if l.get('status') == 'active']
        active_listings.sort(key=lambda x: x['id'])
        start = page * per_page
        end = start + per_page
        return active_listings[start:end], len(active_listings)
    
    def get_listing(self, listing_id):
        data = self.db.read()
        for listing in data['listings']:
            if listing['id'] == listing_id and listing.get('status') == 'active':
                return listing
        return None
    
    def get_user_listings(self, user_id):
        data = self.db.read()
        return [l for l in data['listings'] if l['seller_id'] == user_id and l.get('status') == 'active']
    
    def buy_listing(self, listing_id, buyer_id):
        data = self.db.read()
        
        listing = None
        listing_index = -1
        for i, l in enumerate(data['listings']):
            if l['id'] == listing_id and l.get('status') == 'active':
                listing = l
                listing_index = i
                break
        
        if not listing:
            return {'ok': False, 'msg': '❌ Не найдено'}
        
        if listing['seller_id'] == buyer_id:
            return {'ok': False, 'msg': '❌ Свой нельзя'}
        
        buyer = core.db.get(buyer_id)
        if buyer['balance'] < listing['price']:
            return {'ok': False, 'msg': f'❌ Нужно {fmt(listing["price"])}'}
        
        core.db.update(buyer_id, balance=buyer['balance'] - listing['price'])
        
        seller = core.db.get(listing['seller_id'])
        core.db.update(listing['seller_id'], balance=seller['balance'] + listing['price'])
        
        inv_data = core.shop.inv.read()
        buyer_inv = inv_data.get(str(buyer_id), [])
        
        nft_copy = listing['nft'].copy()
        nft_copy['purchased_at'] = datetime.datetime.now().isoformat()
        nft_copy['unique_id'] = f"{buyer_id}_{nft_copy['item_id']}_{nft_copy.get('global_number', 0)}_{random.randint(1000,9999)}"
        nft_copy['is_upgraded'] = False
        
        buyer_inv.append(nft_copy)
        inv_data[str(buyer_id)] = buyer_inv
        core.shop.inv.write(inv_data)
        
        data['listings'][listing_index]['status'] = 'sold'
        data['listings'][listing_index]['buyer_id'] = buyer_id
        data['listings'][listing_index]['sold_at'] = datetime.datetime.now().isoformat()
        self.db.write(data)
        
        return {'ok': True, 'msg': f'✅ Куплен за {fmt(listing["price"])}', 'nft': nft_copy}
    
    def cancel_listing(self, listing_id, seller_id):
        data = self.db.read()
        
        for i, listing in enumerate(data['listings']):
            if listing['id'] == listing_id and listing.get('status') == 'active':
                if listing['seller_id'] != seller_id:
                    return {'ok': False, 'msg': '❌ Не ваше'}
                
                inv_data = core.shop.inv.read()
                seller_inv = inv_data.get(str(seller_id), [])
                
                nft_copy = listing['nft'].copy()
                nft_copy['purchased_at'] = datetime.datetime.now().isoformat()
                nft_copy['unique_id'] = f"{seller_id}_{nft_copy['item_id']}_{nft_copy.get('global_number', 0)}_{random.randint(1000,9999)}"
                nft_copy['is_upgraded'] = False
                
                seller_inv.append(nft_copy)
                inv_data[str(seller_id)] = seller_inv
                core.shop.inv.write(inv_data)
                
                data['listings'][i]['status'] = 'cancelled'
                data['listings'][i]['cancelled_at'] = datetime.datetime.now().isoformat()
                self.db.write(data)
                
                return {'ok': True, 'msg': '✅ Снято, NFT возвращён'}
        
        return {'ok': False, 'msg': '❌ Не найдено'}

class Events:
    def __init__(self):
        self.db = DB(EVENTS_FILE)
        self.active_event = None
        self._load()
    
    def _load(self):
        data = self.db.read()
        if data and 'active_event' in data:
            event = data['active_event']
            if event and datetime.datetime.fromisoformat(event['end_time']) > datetime.datetime.now():
                self.active_event = event
            else:
                self.active_event = None
                data['active_event'] = None
                self.db.write(data)
    
    def create_event(self, name, duration_seconds, created_by, chat_id):
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
        
        multiplier = 2
        if name == 'crash':
            multiplier = 1.1
        
        event = {
            'name': name,
            'multiplier': multiplier,
            'start_time': datetime.datetime.now().isoformat(),
            'end_time': end_time.isoformat(),
            'created_by': created_by,
            'chat_id': chat_id,
            'active': True
        }
        
        data = self.db.read()
        history = data.get('history', [])
        data = {'active_event': event, 'history': history}
        self.db.write(data)
        self.active_event = event
        return event
    
    def end_event(self):
        if self.active_event:
            data = self.db.read()
            history = data.get('history', [])
            history.append({
                'name': self.active_event['name'],
                'start_time': self.active_event['start_time'],
                'end_time': datetime.datetime.now().isoformat(),
                'multiplier': self.active_event['multiplier']
            })
            if len(history) > 20:
                history = history[-20:]
            
            data['history'] = history
            data['active_event'] = None
            self.db.write(data)
            self.active_event = None
    
    def get_active_event(self):
        if self.active_event:
            if datetime.datetime.fromisoformat(self.active_event['end_time']) < datetime.datetime.now():
                self.end_event()
                return None
            return self.active_event
        return None
    
    def get_remaining_seconds(self):
        if self.active_event:
            end = datetime.datetime.fromisoformat(self.active_event['end_time'])
            remaining = (end - datetime.datetime.now()).total_seconds()
            return max(0, int(remaining))
        return 0
    
    def format_time(self, seconds):
        minutes = seconds // 60
        secs = seconds % 60
        if minutes > 0:
            return f"{minutes}м {secs}с"
        else:
            return f"{secs}с"
    
    def get_history(self):
        return self.db.read().get('history', [])

class AdsManager:
    def __init__(self):
        self.tasks_db = DB(ADS_FILE)
        self.user_tasks_db = DB(USER_TASKS_FILE)
        self._ensure()
    
    def _ensure(self):
        tasks = self.tasks_db.read()
        if not tasks:
            tasks = {
                "tasks": [],
                "next_id": 1
            }
            self.tasks_db.write(tasks)
        
        user_tasks = self.user_tasks_db.read()
        if not user_tasks:
            self.user_tasks_db.write({})
    
    def create_task(self, creator_id, channel_info, subscribers_count, reward_per_user, total_cost):
        tasks = self.tasks_db.read()
        
        task_id = tasks["next_id"]
        tasks["next_id"] += 1
        
        task = {
            "id": task_id,
            "creator_id": creator_id,
            "channel_id": channel_info.get("id"),
            "channel_name": channel_info.get("name"),
            "channel_username": channel_info.get("username"),
            "channel_url": channel_info.get("url"),
            "subscribers_needed": subscribers_count,
            "reward_per_user": reward_per_user,
            "total_cost": total_cost,
            "completed_count": 0,
            "users_completed": [],
            "created_at": datetime.datetime.now().isoformat(),
            "active": True
        }
        
        tasks["tasks"].append(task)
        self.tasks_db.write(tasks)
        
        return {"ok": True, "task_id": task_id, "task": task}
    
    def get_active_tasks(self):
        tasks = self.tasks_db.read()
        return [t for t in tasks["tasks"] if t["active"]]
    
    def get_available_tasks(self, user_id):
        tasks = self.tasks_db.read()
        available = []
        
        for task in tasks["tasks"]:
            if not task["active"]:
                continue
            if task["creator_id"] == user_id:
                continue
            if task["completed_count"] >= task["subscribers_needed"]:
                continue
            if user_id in task["users_completed"]:
                continue
            
            available.append(task)
        
        return available
    
    def get_task(self, task_id):
        tasks = self.tasks_db.read()
        for task in tasks["tasks"]:
            if task["id"] == task_id:
                return task
        return None
    
    def get_user_tasks(self, creator_id):
        tasks = self.tasks_db.read()
        return [t for t in tasks["tasks"] if t["creator_id"] == creator_id]
    
    def deactivate_task(self, task_id, creator_id):
        tasks = self.tasks_db.read()
        for task in tasks["tasks"]:
            if task["id"] == task_id:
                if task["creator_id"] != creator_id and not is_creator(creator_id):
                    return {"ok": False, "msg": "❌ Это не твоё задание"}
                
                task["active"] = False
                task["deactivated_at"] = datetime.datetime.now().isoformat()
                self.tasks_db.write(tasks)
                return {"ok": True, "msg": f"✅ Задание #{task_id} отключено"}
        
        return {"ok": False, "msg": "❌ Задание не найдено"}
    
    def complete_task(self, user_id, task_id):
        tasks = self.tasks_db.read()
        
        for task in tasks["tasks"]:
            if task["id"] == task_id:
                if not task["active"]:
                    return {"ok": False, "msg": "❌ Задание уже неактивно"}
                
                if task["completed_count"] >= task["subscribers_needed"]:
                    return {"ok": False, "msg": "❌ Лимит подписчиков исчерпан"}
                
                if user_id in task["users_completed"]:
                    return {"ok": False, "msg": "❌ Ты уже выполнил это задание"}
                
                task["users_completed"].append(user_id)
                task["completed_count"] += 1
                
                user = core.db.get(user_id)
                core.db.update(user_id, balance=user['balance'] + task['reward_per_user'])
                
                self.tasks_db.write(tasks)
                
                return {
                    "ok": True,
                    "reward": task['reward_per_user'],
                    "task": task,
                    "completed": task['completed_count'],
                    "total": task['subscribers_needed']
                }
        
        return {"ok": False, "msg": "❌ Задание не найдено"}

class Games:
    def __init__(self, db):
        self.db = db
    
    def can(self, uid, amount):
        return self.db.get(uid)['balance'] >= amount
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def coin(self, uid, bet, choice):
        if not self.can(uid, bet):
            return {'ok': False, 'msg': '❌ Не хватает'}
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        result = random.choice(['орёл', 'решка'])
        win = choice == result
        if win:
            win_amount = bet * 2
            final_win = self.apply_event_multiplier(win_amount)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {'ok': True, 'win': True, 'res': result, 'amount': final_win, 'balance': user['balance'] - bet + final_win, 'event': event_bonus}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'res': result, 'amount': bet, 'balance': user['balance'] - bet}
    
    async def slots(self, msg, uid, bet):
        if not self.can(uid, bet):
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        
        slots_msg = await msg.answer_dice(emoji='🎰')
        slots_value = slots_msg.dice.value
        
        if slots_value == 64:
            mult = 10
            win = bet * mult
            final_win = self.apply_event_multiplier(win)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {'ok': True, 'win': True, 'value': slots_value, 'mult': mult, 'amount': final_win, 'balance': user['balance'] - bet + final_win, 'event': event_bonus}
        elif slots_value in [1, 22, 43]:
            mult = 5
            win = bet * mult
            final_win = self.apply_event_multiplier(win)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {'ok': True, 'win': True, 'value': slots_value, 'mult': mult, 'amount': final_win, 'balance': user['balance'] - bet + final_win, 'event': event_bonus}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'value': slots_value, 'amount': bet, 'balance': user['balance'] - bet}
    
    async def dice(self, msg, uid, bet, pred):
        if not self.can(uid, bet):
            return {'ok': False, 'msg': '❌ Не хватает'}
        if pred < 1 or pred > 6:
            return {'ok': False, 'msg': '❌ От 1 до 6'}
        
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        
        dice_msg = await msg.answer_dice(emoji='🎲')
        roll = dice_msg.dice.value
        
        win = pred == roll
        if win:
            win_amount = bet * 6
            final_win = self.apply_event_multiplier(win_amount)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {'ok': True, 'win': True, 'roll': roll, 'amount': final_win, 'balance': user['balance'] - bet + final_win, 'event': event_bonus}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'roll': roll, 'amount': bet, 'balance': user['balance'] - bet}

class BallGames:
    def __init__(self, db):
        self.db = db
        
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    async def play_football(self, msg, uid, bet, choice):
        if not self.can(uid, bet):
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        
        football_msg = await msg.answer_dice(emoji='⚽')
        football_value = football_msg.dice.value
        
        is_goal = football_value >= 3
        result = 'гол' if is_goal else 'мимо'
        win = (choice == 'гол' and is_goal) or (choice == 'мимо' and not is_goal)
        
        if is_goal:
            result_emoji = '⚽'
            result_text = f"ГОЛ! [{football_value}]"
        else:
            result_emoji = '🥅'
            result_text = f"МИМО [{football_value}]"
        
        if win:
            win_amount = bet * 2
            final_win = self.apply_event_multiplier(win_amount)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, 
                          wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {
                'ok': True, 'win': True, 'result': result, 'amount': final_win,
                'balance': user['balance'] - bet + final_win, 'event': event_bonus,
                'emoji': result_emoji, 'value': football_value, 'result_text': result_text
            }
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {
                'ok': True, 'win': False, 'result': result, 'amount': bet,
                'balance': user['balance'] - bet,
                'emoji': result_emoji, 'value': football_value, 'result_text': result_text
            }
    
    async def play_basketball(self, msg, uid, bet, choice):
        if not self.can(uid, bet):
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        
        basketball_msg = await msg.answer_dice(emoji='🏀')
        basketball_value = basketball_msg.dice.value
        
        is_goal = basketball_value >= 4
        result = 'гол' if is_goal else 'мимо'
        win = (choice == 'гол' and is_goal) or (choice == 'мимо' and not is_goal)
        
        if is_goal:
            result_emoji = '🏀'
            result_text = f"ГОЛ! [{basketball_value}]"
        else:
            result_emoji = '🧺'
            result_text = f"МИМО [{basketball_value}]"
        
        if win:
            win_amount = bet * 2
            final_win = self.apply_event_multiplier(win_amount)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, 
                          wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {
                'ok': True, 'win': True, 'result': result, 'amount': final_win,
                'balance': user['balance'] - bet + final_win, 'event': event_bonus,
                'emoji': result_emoji, 'value': basketball_value, 'result_text': result_text
            }
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {
                'ok': True, 'win': False, 'result': result, 'amount': bet,
                'balance': user['balance'] - bet,
                'emoji': result_emoji, 'value': basketball_value, 'result_text': result_text
            }
    
    def can(self, uid, amount):
        return self.db.get(uid)['balance'] >= amount

class CrashGame:
    def __init__(self, db):
        self.db = db
        self.games = {}
    
    def get_min_crash(self):
        event = core.events.get_active_event()
        if event and event['name'] == 'crash':
            return event['multiplier']
        return 1.01
    
    def start(self, uid, bet, target):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        if target < 1.1 or target > 100:
            return {'ok': False, 'msg': '❌ От 1.1 до 100'}
        
        new_balance = user['balance'] - bet
        self.db.update(uid, balance=new_balance)
        
        min_crash = self.get_min_crash()
        r = random.random()
        
        if r < 0.4:
            crash = round(random.uniform(min_crash, 1.5), 2)
        elif r < 0.65:
            crash = round(random.uniform(1.51, 2.5), 2)
        elif r < 0.8:
            crash = round(random.uniform(2.51, 4.0), 2)
        elif r < 0.9:
            crash = round(random.uniform(4.01, 7.0), 2)
        elif r < 0.96:
            crash = round(random.uniform(7.01, 15.0), 2)
        elif r < 0.99:
            crash = round(random.uniform(15.01, 50.0), 2)
        else:
            crash = round(random.uniform(50.01, 100.0), 2)
        
        event = core.events.get_active_event()
        event_mult = event['multiplier'] if event and event['name'] == 'money' else 1
        
        if crash >= target:
            win = int(bet * target)
            final_win = win * event_mult
            self.db.update(uid, balance=new_balance + final_win,
                          games_played=user.get('games_played',0)+1,
                          wins=user.get('wins',0)+1)
            event_bonus = f" (x{event_mult})" if event_mult > 1 else ""
            return {'ok': True, 'win': True, 'crash': crash, 'amount': final_win, 'balance': new_balance + final_win, 'event': event_bonus}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'crash': crash, 'amount': bet, 'balance': new_balance}
    
    def cancel_game(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}

class DartGame:
    def __init__(self, db):
        self.db = db
        
        self.sectors = {
            'центр': {'emoji': '🎯', 'mult': 3, 'name': 'ЦЕНТР'},
            'красное': {'emoji': '🔴', 'mult': 2, 'name': 'КРАСНОЕ'},
            'белое': {'emoji': '⚪', 'mult': 1.5, 'name': 'БЕЛОЕ'},
            'мимо': {'emoji': '💢', 'mult': 1, 'name': 'МИМО'}
        }
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    async def play(self, msg, uid, bet, choice):
        if not self.can(uid, bet):
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        
        dart_msg = await msg.answer_dice(emoji='🎯')
        dart_value = dart_msg.dice.value
        
        if dart_value == 1:
            result = 'мимо'
        elif dart_value == 2:
            result = 'красное'
        elif dart_value == 3:
            result = 'белое'
        elif dart_value == 4:
            result = 'красное'
        elif dart_value == 5:
            result = 'белое'
        elif dart_value == 6:
            result = 'центр'
        
        sector = self.sectors[result]
        win = (choice == result)
        
        if win:
            win_amount = int(bet * sector['mult'])
            final_win = self.apply_event_multiplier(win_amount)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, 
                          wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            
            return {
                'ok': True, 'win': True, 'result': result,
                'amount': final_win, 'balance': user['balance'] - bet + final_win,
                'event': event_bonus, 'value': dart_value,
                'sector': sector, 'bet': bet
            }
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {
                'ok': True, 'win': False, 'result': result,
                'amount': bet, 'balance': user['balance'] - bet,
                'value': dart_value, 'sector': sector, 'bet': bet
            }
    
    def can(self, uid, amount):
        return self.db.get(uid)['balance'] >= amount

class Mines:
    def __init__(self, db):
        self.db = db
        self.games = {}
        self.mults_data = {
            1: [1.01, 1.05, 1.10, 1.15, 1.21, 1.27, 1.34, 1.41, 1.48, 1.56, 1.64, 1.72, 1.81, 1.90, 2.00, 2.10, 2.21, 2.32, 2.44, 2.56, 2.69, 2.82, 2.96, 3.11],
            2: [1.05, 1.15, 1.26, 1.39, 1.53, 1.68, 1.85, 2.04, 2.24, 2.46, 2.71, 2.98, 3.28, 3.61, 3.97, 4.37, 4.81, 5.29, 5.82, 6.40, 7.04, 7.74, 8.51, 9.36],
            3: [1.10, 1.26, 1.45, 1.68, 1.94, 2.24, 2.59, 3.00, 3.47, 4.01, 4.64, 5.37, 6.21, 7.19, 8.32, 9.63, 11.14, 12.89, 14.92, 17.26, 19.97, 23.11, 26.74, 30.94],
            4: [1.15, 1.39, 1.68, 2.04, 2.47, 3.00, 3.64, 4.41, 5.35, 6.49, 7.87, 9.55, 11.58, 14.05, 17.04, 20.67, 25.08, 30.42, 36.90, 44.76, 54.30, 65.86, 79.89, 96.91],
            5: [1.21, 1.53, 1.94, 2.47, 3.14, 3.99, 5.07, 6.45, 8.20, 10.43, 13.26, 16.86, 21.44, 27.26, 34.66, 44.07, 56.04, 71.25, 90.60, 115.20, 146.48, 186.25, 236.83, 301.13],
            6: [1.27, 1.68, 2.24, 3.00, 4.01, 5.37, 7.19, 9.63, 12.89, 17.26, 23.11, 30.94, 41.43, 55.47, 74.27, 99.44, 133.14, 178.25, 238.65, 319.54, 427.86, 572.90, 767.09, 1027.23]
        }
    
    def mults(self, count):
        return self.mults_data.get(count, [1.0] * 24)
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def start(self, uid, bet, mines=1):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        
        if mines < 1 or mines > 6:
            return {'ok': False, 'msg': '❌ Мин от 1 до 6'}
        
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        new_balance = user['balance'] - bet
        self.db.update(uid, balance=new_balance)
        
        field = [['⬜']*5 for _ in range(5)]
        
        mpos = []
        while len(mpos) < mines:
            p = (random.randint(0,4), random.randint(0,4))
            if p not in mpos:
                mpos.append(p)
        
        self.games[uid] = {
            'bet': bet,
            'field': field,
            'mines': mpos,
            'count': mines,
            'opened': [],
            'mult': 1.0,
            'mults': self.mults(mines),
            'won': 0,
            'bal': new_balance
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, r, c):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        if (r,c) in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто'}
        
        if (r,c) in g['mines']:
            for rr,cc in g['mines']:
                g['field'][rr][cc] = '💣'
            g['field'][r][c] = '💥'
            
            opened = len(g['opened'])
            field_copy = [row[:] for row in g['field']]
            bet = g['bet']
            
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            
            del self.games[uid]
            
            return {
                'ok': True, 'over': True, 'win': False,
                'field': field_copy, 'opened': opened, 'bet': bet
            }
        
        g['opened'].append((r,c))
        g['field'][r][c] = '💰'
        opened = len(g['opened'])
        g['mult'] = g['mults'][opened-1] if opened-1 < len(g['mults']) else 2.5
        g['won'] = int(g['bet'] * g['mult'])
        
        if opened >= 25 - g['count']:
            user = self.db.get(uid)
            final_win = self.apply_event_multiplier(g['won'])
            new_bal = g['bal'] + final_win
            self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            
            for rr,cc in g['mines']:
                g['field'][rr][cc] = '💣'
            
            field_copy = [row[:] for row in g['field']]
            mult = g['mult']
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            
            del self.games[uid]
            
            return {
                'ok': True, 'over': True, 'win': True,
                'field': field_copy, 'opened': opened, 'won': final_win,
                'balance': new_bal, 'mult': mult, 'event': event_bonus
            }
        
        return {
            'ok': True, 'over': False, 'field': g['field'],
            'opened': opened, 'mult': g['mult'], 'won': g['won'],
            'max': 25 - g['count']
        }
    
    def cashout(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        if not g['opened']:
            return {'ok': False, 'msg': '❌ Сначала открой клетку'}
        
        user = self.db.get(uid)
        final_win = self.apply_event_multiplier(g['won'])
        new_bal = g['bal'] + final_win
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        
        for rr,cc in g['mines']:
            g['field'][rr][cc] = '💣'
        
        field = [row[:] for row in g['field']]
        won = final_win
        opened = len(g['opened'])
        mult = g['mult']
        event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
        
        del self.games[uid]
        
        return {
            'ok': True, 'won': won, 'balance': new_bal,
            'field': field, 'opened': opened, 'mult': mult,
            'event': event_bonus
        }
    
    def cancel_game(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}
    
    def kb(self, uid, field, active=True):
        kb = []
        for i in range(5):
            row = []
            for j in range(5):
                if field[i][j] in ['💰','💣','💥']:
                    row.append(InlineKeyboardButton(text=field[i][j], callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(text="❓" if active else "⬛", callback_data=f"mines_{uid}_{i}_{j}"))
            kb.append(row)
        if active:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"cashout_{uid}")])
        kb.append([InlineKeyboardButton(text="🎮 Новая", callback_data="mines_new")])
        return InlineKeyboardMarkup(inline_keyboard=kb)

class Tower:
    def __init__(self, db):
        self.db = db
        self.games = {}
        self.base = [1.2, 1.5, 2.0, 2.5, 3.2, 4.0, 5.0, 6.0, 7.0]
    
    def mults(self, mines):
        if mines == 1:
            return self.base
        elif mines == 2:
            return [round(x * 1.4, 2) for x in self.base]
        elif mines == 3:
            return [round(x * 1.8, 2) for x in self.base]
        elif mines == 4:
            return [round(x * 2.2, 2) for x in self.base]
        return self.base
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def start(self, uid, bet, mines=1):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        
        if mines < 1 or mines > 4:
            return {'ok': False, 'msg': '❌ Мин от 1 до 4'}
        
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        
        row = {
            'cells': ['⬜']*5,
            'mines': random.sample(range(5), mines),
            'revealed': False
        }
        
        self.games[uid] = {
            'bet': bet,
            'mines': mines,
            'row': 0,
            'rows': [row],
            'opened': [],
            'mult': 1.0,
            'mults': self.mults(mines),
            'bal': new_bal,
            'won': 0,
            'total_rows': 9
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, r, c):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        
        if r != g['row']:
            return {'ok': False, 'msg': '❌ Можно открывать только текущий ряд'}
        
        if f"{r}_{c}" in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто'}
        
        row = g['rows'][r]
        
        if c in row['mines']:
            for i in range(5):
                row['cells'][i] = '💣' if i in row['mines'] else '⬛'
            row['cells'][c] = '💥'
            
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'over': True, 'mine': True, 'row_data': row, 'bet': g['bet']}
        
        g['opened'].append(f"{r}_{c}")
        row['cells'][c] = '🟩'
        g['mult'] = g['mults'][r]
        g['won'] = int(g['bet'] * g['mult'])
        
        if r >= g['total_rows'] - 1:
            user = self.db.get(uid)
            final_win = self.apply_event_multiplier(g['won'])
            new_bal = g['bal'] + final_win
            self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            del self.games[uid]
            return {'ok': True, 'over': True, 'win': True, 'won': final_win, 'mult': g['mult'], 'rows': r+1, 'balance': new_bal, 'event': event_bonus}
        
        g['row'] += 1
        
        if len(g['rows']) <= g['row']:
            g['rows'].append({
                'cells': ['⬜']*5,
                'mines': random.sample(range(5), g['mines']),
                'revealed': False
            })
        
        return {'ok': True, 'over': False, 'row': r, 'col': c, 'next': g['row'],
                'mult': g['mult'], 'won': g['won']}
    
    def cashout(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        if not g['opened']:
            return {'ok': False, 'msg': '❌ Сначала открой клетку'}
        
        user = self.db.get(uid)
        final_win = self.apply_event_multiplier(g['won'])
        new_bal = g['bal'] + final_win
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
        del self.games[uid]
        return {'ok': True, 'won': final_win, 'mult': g['mult'], 'rows': g['row'], 'balance': new_bal, 'event': event_bonus}
    
    def cancel_game(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}
    
    def kb(self, uid, g):
        kb = []
        for r in range(g['total_rows'] - 1, -1, -1):
            if r < len(g['rows']):
                row = g['rows'][r]
                btns = []
                if r > g['row']:
                    for c in range(5):
                        btns.append(InlineKeyboardButton(text="❓", callback_data="ignore"))
                elif r == g['row']:
                    for c in range(5):
                        if f"{r}_{c}" in g['opened']:
                            btns.append(InlineKeyboardButton(text="💰", callback_data="ignore"))
                        else:
                            btns.append(InlineKeyboardButton(text="❓", callback_data=f"tower_{uid}_{r}_{c}"))
                else:
                    for c in range(5):
                        if f"{r}_{c}" in g['opened']:
                            btns.append(InlineKeyboardButton(text="💰", callback_data="ignore"))
                        else:
                            btns.append(InlineKeyboardButton(text="❓", callback_data="ignore"))
                kb.append(btns)
            else:
                btns = [InlineKeyboardButton(text="⬛", callback_data="ignore") for _ in range(5)]
                kb.append(btns)
        
        if g['opened']:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"tower_cash_{uid}")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)

class Diamonds:
    def __init__(self, db):
        self.db = db
        self.games = {}
        self.base = [1.3, 1.7, 2.2, 2.8, 3.5, 4.3, 5.2, 6.2, 7.3]
    
    def mults(self, mines):
        if mines == 1:
            return self.base
        elif mines == 2:
            return [round(x * 1.5, 2) for x in self.base]
        return self.base
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def start(self, uid, bet, mines=1):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        
        if mines < 1 or mines > 2:
            return {'ok': False, 'msg': '❌ Мин от 1 до 2'}
        
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        
        row = {
            'cells': ['⬜']*3,
            'mines': random.sample(range(3), mines),
            'revealed': False
        }
        
        self.games[uid] = {
            'bet': bet,
            'mines': mines,
            'row': 0,
            'rows': [row],
            'opened': [],
            'mult': 1.0,
            'mults': self.mults(mines),
            'bal': new_bal,
            'won': 0
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, r, c):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        
        if r != g['row']:
            return {'ok': False, 'msg': '❌ Можно открывать только текущий ряд'}
        
        if f"{r}_{c}" in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто'}
        
        row = g['rows'][r]
        
        if c in row['mines']:
            for i in range(3):
                row['cells'][i] = '💣' if i in row['mines'] else '⬛'
            row['cells'][c] = '💥'
            
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'over': True, 'mine': True, 'row_data': row, 'bet': g['bet']}
        
        g['opened'].append(f"{r}_{c}")
        row['cells'][c] = '💎'
        g['mult'] = g['mults'][r]
        g['won'] = int(g['bet'] * g['mult'])
        
        if r >= 8:
            user = self.db.get(uid)
            final_win = self.apply_event_multiplier(g['won'])
            new_bal = g['bal'] + final_win
            self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            del self.games[uid]
            return {'ok': True, 'over': True, 'win': True, 'won': final_win, 'mult': g['mult'], 'rows': r+1, 'balance': new_bal, 'event': event_bonus}
        
        g['row'] += 1
        
        if len(g['rows']) <= g['row']:
            g['rows'].append({
                'cells': ['⬜']*3,
                'mines': random.sample(range(3), g['mines']),
                'revealed': False
            })
        
        return {'ok': True, 'over': False, 'row': r, 'col': c, 'next': g['row'],
                'mult': g['mult'], 'won': g['won']}
    
    def cashout(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        if not g['opened']:
            return {'ok': False, 'msg': '❌ Сначала открой клетку'}
        
        user = self.db.get(uid)
        final_win = self.apply_event_multiplier(g['won'])
        new_bal = g['bal'] + final_win
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
        del self.games[uid]
        return {'ok': True, 'won': final_win, 'mult': g['mult'], 'rows': g['row'], 'balance': new_bal, 'event': event_bonus}
    
    def cancel_game(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}
    
    def kb(self, uid, g):
        kb = []
        for r in range(len(g['rows'])):
            row = g['rows'][r]
            btns = []
            if r < g['row']:
                for c in range(3):
                    if f"{r}_{c}" in g['opened']:
                        btns.append(InlineKeyboardButton(text="💎", callback_data="ignore"))
                    else:
                        btns.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            elif r == g['row']:
                for c in range(3):
                    btns.append(InlineKeyboardButton(text="❓", callback_data=f"diamonds_{uid}_{r}_{c}"))
            else:
                for c in range(3):
                    btns.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            kb.append(btns)
        
        if g['opened']:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"diamonds_cash_{uid}")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)

class Quack:
    def __init__(self, db):
        self.db = db
        self.games = {}
        
        # Множители по рядам (снизу вверх)
        self.multipliers = [1.21, 2.0, 5.05, 25.0]
        
        # Количество мин по рядам (1-й ряд снизу - 1 мина, 4-й ряд - 4 мины)
        self.mines_count = [1, 2, 3, 4]
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def start(self, uid, bet):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        
        # Создаём все ряды
        rows = []
        for row_idx in range(4):
            mines = self.mines_count[row_idx]
            row = {
                'cells': ['⬜'] * 5,
                'mines': random.sample(range(5), mines),
                'revealed': False
            }
            rows.append(row)
        
        self.games[uid] = {
            'bet': bet,
            'row': 0,  # Текущий ряд (0 - первый снизу)
            'rows': rows,
            'opened': [],
            'mult': 1.0,
            'bal': new_bal,
            'won': 0
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, r, c):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        
        if r != g['row']:
            return {'ok': False, 'msg': '❌ Можно открывать только текущий ряд'}
        
        cell_key = f"{r}_{c}"
        if cell_key in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто'}
        
        row = g['rows'][r]
        
        # Проверка на мину
        if c in row['mines']:
            # Показываем все мины в ряду
            for i in range(5):
                if i in row['mines']:
                    row['cells'][i] = '💣'
                else:
                    row['cells'][i] = '⬛'
            row['cells'][c] = '💥'
            
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played', 0) + 1)
            del self.games[uid]
            
            mines_word = "мина" if self.mines_count[r] == 1 else "мины"
            
            return {
                'ok': True, 
                'over': True, 
                'mine': True, 
                'row_data': row,
                'row_idx': r + 1,
                'mines_count': self.mines_count[r],
                'mines_word': mines_word,
                'bet': g['bet']
            }
        
        # Открываем клетку
        g['opened'].append(cell_key)
        row['cells'][c] = '🟩'
        g['mult'] = self.multipliers[r]
        g['won'] = int(g['bet'] * g['mult'])
        
        # Проверка на победу (открыли последний ряд)
        if r >= 3:  # 4-й ряд (индекс 3)
            user = self.db.get(uid)
            final_win = self.apply_event_multiplier(g['won'])
            new_bal = g['bal'] + final_win
            self.db.update(uid, balance=new_bal,
                          games_played=user.get('games_played', 0) + 1,
                          wins=user.get('wins', 0) + 1)
            
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            
            del self.games[uid]
            
            return {
                'ok': True, 
                'over': True, 
                'win': True, 
                'won': final_win, 
                'mult': g['mult'],
                'row': r + 1,
                'balance': new_bal,
                'event': event_bonus
            }
        
        # Переходим к следующему ряду
        g['row'] += 1
        
        return {
            'ok': True, 
            'over': False, 
            'row': r, 
            'col': c, 
            'next': g['row'] + 1,
            'mult': g['mult'], 
            'won': g['won']
        }
    
    def cashout(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        
        if not g['opened']:
            return {'ok': False, 'msg': '❌ Сначала открой клетку'}
        
        user = self.db.get(uid)
        final_win = self.apply_event_multiplier(g['won'])
        new_bal = g['bal'] + final_win
        self.db.update(uid, balance=new_bal,
                      games_played=user.get('games_played', 0) + 1,
                      wins=user.get('wins', 0) + 1)
        
        event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
        
        del self.games[uid]
        
        return {
            'ok': True, 
            'won': final_win, 
            'mult': g['mult'], 
            'row': g['row'],
            'balance': new_bal,
            'event': event_bonus
        }
    
    def cancel_game(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}
    
    def kb(self, uid, g):
        kb = []
        
        # Показываем ряды сверху вниз (как в башне)
        for r in range(3, -1, -1):
            row = g['rows'][r]
            btns = []
            
            if r < g['row']:
                # Ряды, которые уже пройдены
                for c in range(5):
                    if f"{r}_{c}" in g['opened']:
                        btns.append(InlineKeyboardButton(text="🟩", callback_data="ignore"))
                    else:
                        btns.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            elif r == g['row']:
                # Текущий ряд
                for c in range(5):
                    if f"{r}_{c}" in g['opened']:
                        btns.append(InlineKeyboardButton(text="🟩", callback_data="ignore"))
                    else:
                        btns.append(InlineKeyboardButton(text="🟦", callback_data=f"quack_{uid}_{r}_{c}"))
            else:
                # Ряды, до которых ещё не дошли
                for c in range(5):
                    btns.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            
            kb.append(btns)
        
        # Добавляем информацию о минах
        mines_info = f"💣 Мин в ряду: {self.mines_count[g['row']]}"
        kb.append([InlineKeyboardButton(text=mines_info, callback_data="ignore")])
        
        if g['opened']:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"quack_cash_{uid}")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)
    
    def get_info(self):
        info = "🐸 КВАК\n\n"
        info += "Ряды снизу вверх:\n"
        info += "1️⃣ ряд (1 мина) - x1.21\n"
        info += "2️⃣ ряд (2 мины) - x2.0\n"
        info += "3️⃣ ряд (3 мины) - x5.05\n"
        info += "4️⃣ ряд (4 мины) - x25.0\n\n"
        info += "В каждом ряду можно открыть только 1 клетку!\n"
        info += "Если откроешь мину - проигрыш"
        return info

class Pyramid:
    def __init__(self, db):
        self.db = db
        self.games = {}
        
        self.multipliers = {
            1: [1.7, 2.3, 3.1, 4.2, 5.7, 7.7, 10.4, 14.0, 18.9, 25.5, 34.4, 46.4],
            2: [1.5, 2.0, 2.7, 3.6, 4.9, 6.6, 8.9, 12.0, 16.2, 21.9, 29.6, 40.0],
            3: [1.31, 1.74, 2.32, 3.10, 4.13, 5.51, 7.34, 9.79, 13.05, 17.40, 23.20, 30.93]
        }
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def start(self, uid, bet, doors=3):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        
        if doors < 1 or doors > 3:
            return {'ok': False, 'msg': '❌ Дверей от 1 до 3'}
        
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        
        level = self.generate_level(doors)
        
        self.games[uid] = {
            'bet': bet,
            'doors': doors,
            'level': 0,
            'levels': [level],
            'opened': [],
            'mult': 1.0,
            'multipliers': self.multipliers[doors],
            'bal': new_bal,
            'won': 0
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def generate_level(self, doors):
        cells = ['🚪'] * 4
        safe_positions = random.sample(range(4), doors)
        return {
            'cells': cells,
            'safe': safe_positions,
            'revealed': False
        }
    
    def open(self, uid, level_idx, cell_idx):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        
        if level_idx != g['level']:
            return {'ok': False, 'msg': '❌ Можно открывать только текущий уровень'}
        
        cell_key = f"{level_idx}_{cell_idx}"
        if cell_key in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто'}
        
        level = g['levels'][level_idx]
        
        if cell_idx not in level['safe']:
            for i in range(4):
                if i in level['safe']:
                    level['cells'][i] = '🚪'
                else:
                    level['cells'][i] = '💀'
            level['cells'][cell_idx] = '💥'
            
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played', 0) + 1)
            
            field = self.format_field(g['levels'])
            
            del self.games[uid]
            
            return {
                'ok': True, 'over': True, 'win': False,
                'field': field, 'level': level_idx + 1, 'bet': g['bet']
            }
        
        g['opened'].append(cell_key)
        level['cells'][cell_idx] = '✅'
        level['revealed'] = True
        
        g['mult'] = g['multipliers'][level_idx]
        g['won'] = int(g['bet'] * g['mult'])
        
        if level_idx >= 11:
            user = self.db.get(uid)
            final_win = self.apply_event_multiplier(g['won'])
            new_bal = g['bal'] + final_win
            self.db.update(uid, balance=new_bal,
                          games_played=user.get('games_played', 0) + 1,
                          wins=user.get('wins', 0) + 1)
            
            field = self.format_field(g['levels'])
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            
            del self.games[uid]
            
            return {
                'ok': True, 'over': True, 'win': True,
                'field': field, 'won': final_win, 'mult': g['mult'],
                'level': level_idx + 1, 'balance': new_bal, 'event': event_bonus
            }
        
        g['level'] += 1
        
        if len(g['levels']) <= g['level']:
            g['levels'].append(self.generate_level(g['doors']))
        
        field = self.format_field(g['levels'])
        
        return {
            'ok': True, 'over': False, 'field': field,
            'level': level_idx + 1, 'next': g['level'] + 1,
            'mult': g['mult'], 'won': g['won'], 'max_level': 12
        }
    
    def cashout(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        
        if g['level'] == 0:
            return {'ok': False, 'msg': '❌ Сначала открой дверь'}
        
        user = self.db.get(uid)
        final_win = self.apply_event_multiplier(g['won'])
        new_bal = g['bal'] + final_win
        self.db.update(uid, balance=new_bal,
                      games_played=user.get('games_played', 0) + 1,
                      wins=user.get('wins', 0) + 1)
        
        field = self.format_field(g['levels'])
        event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
        
        del self.games[uid]
        
        return {
            'ok': True, 'won': final_win, 'mult': g['mult'],
            'level': g['level'], 'balance': new_bal,
            'field': field, 'event': event_bonus
        }
    
    def cancel_game(self, uid):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}
    
    def format_field(self, levels):
        result = []
        for level_idx, level in enumerate(levels):
            cells = level['cells']
            result.append(f"{level_idx + 1}:")
            result.append(f"{cells[0]} {cells[1]}")
            result.append(f"{cells[2]} {cells[3]}")
            result.append("")
        return "\n".join(result)
    
    def kb(self, uid, game):
        kb = []
        current_level = game['levels'][game['level']]
        
        row1 = []
        row2 = []
        
        for i in range(4):
            if f"{game['level']}_{i}" in game['opened']:
                btn = InlineKeyboardButton(text="✅", callback_data="ignore")
            else:
                btn = InlineKeyboardButton(text="🚪", callback_data=f"pyramid_{uid}_{game['level']}_{i}")
            
            if i < 2:
                row1.append(btn)
            else:
                row2.append(btn)
        
        kb.append(row1)
        kb.append(row2)
        
        if game['opened']:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"pyramid_cash_{uid}")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)

class Roulette:
    def __init__(self, db):
        self.db = db
        self.red = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def play(self, uid, bet, btype, val=None):
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        self.db.update(uid, balance=user['balance'] - bet)
        num = random.randint(0,36)
        color = '🟢' if num == 0 else ('🔴' if num in self.red else '⚫')
        win = False
        mult = 0
        if btype == 'even' and num != 0 and num % 2 == 0:
            win, mult = True, 2
        elif btype == 'odd' and num != 0 and num % 2 == 1:
            win, mult = True, 2
        elif btype == 'red' and color == '🔴':
            win, mult = True, 2
        elif btype == 'black' and color == '⚫':
            win, mult = True, 2
        elif btype == '1-12' and 1 <= num <= 12:
            win, mult = True, 3
        elif btype == '13-24' and 13 <= num <= 24:
            win, mult = True, 3
        elif btype == '25-36' and 25 <= num <= 36:
            win, mult = True, 3
        elif btype == 'zero' and num == 0:
            win, mult = True, 36
        elif btype == 'number' and val is not None and num == val:
            win, mult = True, 36
        if win:
            win_amount = bet * mult
            final_win = self.apply_event_multiplier(win_amount)
            self.db.update(uid, balance=user['balance'] - bet + final_win,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {'ok': True, 'win': True, 'num': num, 'color': color, 'amount': final_win, 'mult': mult, 'balance': user['balance'] - bet + final_win, 'event': event_bonus}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'num': num, 'color': color, 'amount': bet, 'balance': user['balance'] - bet}

class Gold:
    def __init__(self, db):
        self.db = db
        self.games = {}
        self.mults = [2,4,8,16,32,64,128,256,512,1024,2048,4096]
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def start(self, uid, bet, chat_id=None):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        self.games[uid] = {
            'bet': bet,
            'level': 0,
            'won': 0,
            'bal': new_bal,
            'history': [],
            'chat_id': chat_id,
            'uid': uid
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def choose(self, uid, choice, chat_id=None):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Не ваш чат'}
        
        money = random.randint(1,2)
        win = choice == money
        g['history'].append({'level': g['level']+1, 'choice': choice, 'money': money, 'win': win})
        
        if win:
            g['level'] += 1
            g['won'] = g['bet'] * self.mults[g['level']-1]
            if g['level'] >= 12:
                user = self.db.get(uid)
                final_win = self.apply_event_multiplier(g['won'])
                new_bal = g['bal'] + final_win
                self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
                event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
                del self.games[uid]
                return {'ok': True, 'win': True, 'max': True, 'won': final_win, 'mult': self.mults[g['level']-1], 'level': g['level'], 'balance': new_bal, 'event': event_bonus}
            return {'ok': True, 'win': True, 'level': g['level'], 'mult': self.mults[g['level']-1], 'won': g['won'], 'money': money, 'choice': choice, 'game_over': False}
        else:
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'win': False, 'level': g['level'], 'bet': g['bet'], 'money': money, 'choice': choice, 'game_over': True, 'mult': self.mults[g['level']] if g['level'] < 12 else self.mults[g['level']-1]}
    
    def cashout(self, uid, chat_id=None):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Не ваш чат'}
        
        if g['level'] == 0:
            return {'ok': False, 'msg': '❌ Сначала выбери сторону'}
        
        user = self.db.get(uid)
        final_win = self.apply_event_multiplier(g['won'])
        new_bal = g['bal'] + final_win
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
        del self.games[uid]
        return {'ok': True, 'won': final_win, 'level': g['level'], 'mult': self.mults[g['level']-1], 'balance': new_bal, 'event': event_bonus}
    
    def cancel_game(self, uid, chat_id=None):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Не ваш чат'}
        
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}
    
    def kb(self, uid, g):
        kb = [[
            InlineKeyboardButton(text="⬅️ Левая", callback_data=f"gold_left_{uid}"),
            InlineKeyboardButton(text="➡️ Правая", callback_data=f"gold_right_{uid}")
        ]]
        if g['level'] > 0:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"gold_cash_{uid}")])
        return InlineKeyboardMarkup(inline_keyboard=kb)
    
    def display(self, g, res=None):
        loss = res and not res.get('win', False) and res.get('game_over', False)
        text = "❌ Ты проиграл\n" if loss else "💰 Золото\n\n"
        for i in range(12,0,-1):
            mult = self.mults[i-1]
            win = g['bet'] * mult
            if i <= g['level']:
                hist = next((h for h in g.get('history',[]) if h['level'] == i), None)
                if hist and hist['win']:
                    text += f"|💸|🧨| {fmt(win)} ({mult}x)\n" if hist['choice'] == 1 else f"|🧨|💸| {fmt(win)} ({mult}x)\n"
                else:
                    text += f"|💸|🧨| {fmt(win)} ({mult}x)\n" if i % 2 == 0 else f"|🧨|💸| {fmt(win)} ({mult}x)\n"
            elif i == g['level'] + 1 and loss:
                text += f"|💥|💸| {fmt(win)} ({mult}x)\n" if res and res.get('choice') == 1 else f"|💸|💥| {fmt(win)} ({mult}x)\n"
            else:
                text += f"|❓|❓| ??? ({mult}x)\n"
        return text

class Risk:
    def __init__(self, db):
        self.db = db
        self.games = {}
        self.mults = [1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35]
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def start(self, uid, bet, chat_id=None):
        if uid in self.games:
            return {'ok': False, 'msg': '❌ Игра уже идёт'}
        user = self.db.get(uid)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Не хватает'}
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        cells = []
        win_idx = random.sample(range(6), 3)
        for i in range(6):
            if i in win_idx:
                cells.append({'type': 'win', 'mult': random.choice(self.mults), 'revealed': False})
            else:
                cells.append({'type': 'bomb', 'revealed': False})
        random.shuffle(cells)
        self.games[uid] = {
            'bet': bet,
            'level': 0,
            'cells': cells,
            'won': 0,
            'total_mult': 0.0,
            'bal': new_bal,
            'opened': [],
            'win_cells_opened': 0,
            'chat_id': chat_id,
            'uid': uid
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, idx, chat_id=None):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Не ваш чат'}
        
        if idx in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто'}
        
        cell = g['cells'][idx]
        cell['revealed'] = True
        g['opened'].append(idx)
        
        if cell['type'] == 'bomb':
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'win': False, 'cell': cell, 'game_over': True}
        
        g['level'] += 1
        g['win_cells_opened'] += 1
        g['total_mult'] += cell['mult']
        g['won'] = int(g['bet'] * g['total_mult'])
        
        if g['win_cells_opened'] >= 3:
            user = self.db.get(uid)
            final_win = self.apply_event_multiplier(g['won'])
            new_bal = g['bal'] + final_win
            self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            del self.games[uid]
            return {'ok': True, 'win': True, 'max': True, 'won': final_win, 'total_mult': g['total_mult'], 'balance': new_bal, 'event': event_bonus}
        
        return {'ok': True, 'win': True, 'cell': cell, 'level': g['level'], 'total_mult': g['total_mult'], 'won': g['won']}
    
    def cashout(self, uid, chat_id=None):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Не ваш чат'}
        
        if g['level'] == 0:
            return {'ok': False, 'msg': '❌ Сначала открой клетку'}
        
        user = self.db.get(uid)
        final_win = self.apply_event_multiplier(g['won'])
        new_bal = g['bal'] + final_win
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
        del self.games[uid]
        return {'ok': True, 'won': final_win, 'level': g['level'], 'total_mult': g['total_mult'], 'balance': new_bal, 'event': event_bonus}
    
    def cancel_game(self, uid, chat_id=None):
        if uid not in self.games:
            return {'ok': False, 'msg': '❌ Нет игры'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Не ваш чат'}
        
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Отмена, {fmt(g["bet"])} возвращено'}
    
    def kb(self, uid, g):
        kb = []
        row1, row2 = [], []
        for i, cell in enumerate(g['cells']):
            text = "❓"
            if cell['revealed']:
                text = f"✅ {cell['mult']}x" if cell['type'] == 'win' else "💥"
            btn = InlineKeyboardButton(text=text, callback_data=f"risk_cell_{uid}_{i}")
            if i < 3:
                row1.append(btn)
            else:
                row2.append(btn)
        kb.append(row1)
        kb.append(row2)
        if g['level'] > 0 and g['win_cells_opened'] < 3:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"risk_cash_{uid}")])
        return InlineKeyboardMarkup(inline_keyboard=kb)
    
    def display(self, g):
        return f"🎲 Риск\n\n💰 {fmt(g['bet'])}\n📊 {g['level']}/3\n📈 x{g['total_mult']:.2f}\n💎 {fmt(g['won'])}"

class KNBRussian:
    def __init__(self):
        self.duels = {}
        self.choices = {'камень': '🪨', 'ножницы': '✂️', 'бумага': '📄'}
        self.choices_list = ['камень', 'ножницы', 'бумага']
        self.win_rules = {
            'камень': 'ножницы',
            'ножницы': 'бумага',
            'бумага': 'камень'
        }
    
    def apply_event_multiplier(self, win_amount):
        event = core.events.get_active_event()
        if event and event['name'] == 'money':
            return win_amount * event['multiplier']
        return win_amount
    
    def generate_duel_id(self):
        return random.randint(1000, 9999)
    
    def create_duel(self, creator_id, bet, chat_id, message_id=None):
        duel_id = self.generate_duel_id()
        self.duels[duel_id] = {
            'creator_id': creator_id,
            'bet': bet,
            'chat_id': chat_id,
            'message_id': message_id,
            'status': 'waiting',
            'creator_choice': None,
            'opponent_id': None,
            'opponent_choice': None,
            'created_at': datetime.datetime.now().isoformat()
        }
        return duel_id
    
    def join_duel(self, duel_id, opponent_id):
        if duel_id not in self.duels:
            return {'ok': False, 'msg': '❌ Дуэль не найдена'}
        
        duel = self.duels[duel_id]
        if duel['status'] != 'waiting':
            return {'ok': False, 'msg': '❌ Уже занято'}
        
        if duel['creator_id'] == opponent_id:
            return {'ok': False, 'msg': '❌ Нельзя с собой'}
        
        duel['opponent_id'] = opponent_id
        duel['status'] = 'creator_choice'
        return {'ok': True, 'duel': duel}
    
    def get_duel(self, duel_id):
        return self.duels.get(duel_id)
    
    def make_choice(self, duel_id, user_id, choice):
        if duel_id not in self.duels:
            return {'ok': False, 'msg': '❌ Дуэль не найдена'}
        
        duel = self.duels[duel_id]
        
        if duel['status'] == 'creator_choice' and user_id == duel['creator_id']:
            duel['creator_choice'] = choice
            duel['status'] = 'opponent_choice'
            return {'ok': True, 'next': 'opponent', 'duel': duel}
        
        elif duel['status'] == 'opponent_choice' and user_id == duel['opponent_id']:
            duel['opponent_choice'] = choice
            return self.determine_winner(duel)
        
        return {'ok': False, 'msg': '❌ Не твой ход'}
    
    def determine_winner(self, duel):
        c_choice = duel['creator_choice']
        o_choice = duel['opponent_choice']
        
        if c_choice == o_choice:
            winner = 'draw'
            result_msg = "🤝 Ничья"
        elif self.win_rules[c_choice] == o_choice:
            winner = duel['creator_id']
            win_amount = duel['bet'] * 2
            final_win = self.apply_event_multiplier(win_amount)
            result_msg = f"🎉 Победил создатель +{fmt(final_win)}"
            if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money':
                result_msg += f" (x{core.events.get_active_event()['multiplier']})"
        else:
            winner = duel['opponent_id']
            win_amount = duel['bet'] * 2
            final_win = self.apply_event_multiplier(win_amount)
            result_msg = f"🎉 Победил противник +{fmt(final_win)}"
            if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money':
                result_msg += f" (x{core.events.get_active_event()['multiplier']})"
        
        duel['status'] = 'finished'
        return {'ok': True, 'winner': winner, 'result_msg': result_msg, 'duel': duel}
    
    def delete_duel(self, duel_id):
        if duel_id in self.duels:
            del self.duels[duel_id]
    
    def bot_choice(self):
        return random.choice(self.choices_list)
    
    def get_emoji(self, choice):
        return self.choices.get(choice, '❓')
    
    def vs_bot(self, player_choice, bot_choice, bet):
        if player_choice == bot_choice:
            return {'result': 'draw', 'msg': f"🤝 Ничья, {fmt(bet)} возвращено", 'amount': bet}
        elif self.win_rules[player_choice] == bot_choice:
            win_amount = bet * 2
            final_win = self.apply_event_multiplier(win_amount)
            event_bonus = f" (x{core.events.get_active_event()['multiplier']})" if core.events.get_active_event() and core.events.get_active_event()['name'] == 'money' else ""
            return {'result': 'win', 'msg': f"🎉 +{fmt(final_win)}{event_bonus}", 'amount': final_win}
        else:
            return {'result': 'lose', 'msg': f"❌ -{fmt(bet)}", 'amount': 0}

class Bank:
    def __init__(self):
        self.db = DB(BANK_DATA_FILE)
        self.settings = DB(BANK_SETTINGS_FILE)
        if not self.settings.read():
            self.settings.write({'deposit_rates': {'7':3.0,'14':4.5,'30':6.0,'90':8.0,'180':10.0,'365':12.0},
                                 'loan_rates': {'7':5.0,'14':7.0,'30':10.0,'90':12.0,'180':15.0,'365':20.0},
                                 'max_loan_amount': 1000000, 'min_credit_score': 300})
    
    def get(self, uid):
        data = self.db.read()
        uid = str(uid)
        if uid not in data:
            data[uid] = {'card_balance': 0, 'deposits': [], 'loans': [], 'credit_history': 500}
            self.db.write(data)
        return data[uid]
    
    def update(self, uid, **kwargs):
        data = self.db.read()
        uid = str(uid)
        if uid not in data:
            data[uid] = self.get(uid)
        data[uid].update(kwargs)
        self.db.write(data)
    
    def card_deposit(self, uid, amount, main_bal):
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Сумма > 0'}
        if main_bal < amount:
            return {'ok': False, 'msg': '❌ Не хватает'}
        b = self.get(uid)
        self.update(uid, card_balance=b['card_balance'] + amount)
        return {'ok': True, 'msg': f'✅ На карту +{fmt(amount)}'}
    
    def card_withdraw(self, uid, amount, main_bal):
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Сумма > 0'}
        b = self.get(uid)
        if b['card_balance'] < amount:
            return {'ok': False, 'msg': '❌ Не хватает на карте'}
        self.update(uid, card_balance=b['card_balance'] - amount)
        return {'ok': True, 'msg': f'✅ С карты -{fmt(amount)}'}
    
    def create_deposit(self, uid, amount, days, main_bal):
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Сумма > 0'}
        if main_bal < amount:
            return {'ok': False, 'msg': '❌ Не хватает'}
        rates = self.settings.read()['deposit_rates']
        if str(days) not in rates:
            return {'ok': False, 'msg': '❌ Неверный срок'}
        b = self.get(uid)
        dep = {'id': f"dep_{uid}_{len(b['deposits'])}_{random.randint(100,999)}", 'amount': amount, 'days': days,
               'rate': rates[str(days)], 'start_date': datetime.datetime.now().isoformat(),
               'end_date': (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(), 'status': 'active'}
        b['deposits'].append(dep)
        self.update(uid, deposits=b['deposits'])
        return {'ok': True, 'msg': f'✅ Вклад открыт, доход {fmt(int(amount * rates[str(days)] / 100))}'}
    
    def close_deposit(self, uid, dep_id):
        b = self.get(uid)
        for i, d in enumerate(b['deposits']):
            if d['id'] == dep_id and d['status'] == 'active':
                b['deposits'][i]['status'] = 'closed_early'
                self.update(uid, deposits=b['deposits'])
                return {'ok': True, 'amount': d['amount']}
        return {'ok': False, 'msg': '❌ Вклад не найден'}
    
    def create_loan(self, uid, amount, days, main_bal):
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Сумма > 0'}
        
        b = self.get(uid)
        active_loans = [l for l in b['loans'] if l['status'] == 'active']
        if len(active_loans) > 0:
            return {'ok': False, 'msg': '❌ Сначала закрой текущий кредит'}
        
        s = self.settings.read()
        if str(days) not in s['loan_rates']:
            return {'ok': False, 'msg': '❌ Доступно: 7,14,30,90,180,365'}
        if amount > s['max_loan_amount']:
            return {'ok': False, 'msg': f'❌ Макс {fmt(s["max_loan_amount"])}'}
        if b['credit_history'] < s['min_credit_score']:
            return {'ok': False, 'msg': f'❌ Низкий рейтинг {b["credit_history"]}'}
        
        total = int(amount * (1 + s['loan_rates'][str(days)] / 100))
        loan = {'id': f"loan_{uid}_{len(b['loans'])}_{random.randint(100,999)}", 'amount': amount, 'days': days,
                'rate': s['loan_rates'][str(days)], 'total_to_return': total, 'remaining': total,
                'daily_payment': total // days, 'start_date': datetime.datetime.now().isoformat(),
                'end_date': (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(), 'status': 'active'}
        b['loans'].append(loan)
        self.update(uid, loans=b['loans'])
        return {'ok': True, 'msg': f'✅ Кредит одобрен, к возврату {fmt(total)}'}
    
    def pay_loan(self, uid, loan_id, amount, main_bal):
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Сумма > 0'}
        if main_bal < amount:
            return {'ok': False, 'msg': '❌ Не хватает'}
        b = self.get(uid)
        for i, l in enumerate(b['loans']):
            if l['id'] == loan_id and l['status'] == 'active':
                if amount > l['remaining']:
                    amount = l['remaining']
                l['remaining'] -= amount
                if l['remaining'] <= 0:
                    l['status'] = 'paid'
                    b['credit_history'] = min(1000, b['credit_history'] + 50)
                self.update(uid, loans=b['loans'], credit_history=b['credit_history'])
                return {'ok': True, 'msg': f'✅ Оплачено {fmt(amount)}'}
        return {'ok': False, 'msg': '❌ Кредит не найден'}
    
    def menu(self, uid):
        b = self.get(uid)
        active_deps = [d for d in b['deposits'] if d['status'] == 'active']
        active_loans = [l for l in b['loans'] if l['status'] == 'active']
        loans_info = f"{len(active_loans)}/1 на {fmt(sum(l['remaining'] for l in active_loans))}" if active_loans else "0/1"
        return f"🏦 Банк\n\n💳 {fmt(b['card_balance'])}\n📊 {b['credit_history']}/1000\n\n💰 Вкладов: {len(active_deps)} на {fmt(sum(d['amount'] for d in active_deps))}\n💸 Кредитов: {loans_info}"

class BotCore:
    def __init__(self):
        self.db = UserDB()
        self.promo = PromoDB()
        self.shop = ShopDB()
        self.status = StatusShop()
        self.bank = Bank()
        self.market = Market()
        self.ban = BanDB()
        self.admins = AdminDB()
        self.logs = AdminLogs()
        self.events = Events()
        self.ads = AdsManager()
        self.games = Games(self.db)
        self.ball_games = BallGames(self.db)
        self.crash = CrashGame(self.db)
        self.dart = DartGame(self.db)
        self.mines = Mines(self.db)
        self.tower = Tower(self.db)
        self.diamonds = Diamonds(self.db)
        self.quack = Quack(self.db)
        self.pyramid = Pyramid(self.db)
        self.roulette = Roulette(self.db)
        self.gold = Gold(self.db)
        self.risk = Risk(self.db)
        self.knb = KNBRussian()
    
    def parse_bet(self, text, bal=None):
        if not text:
            return 0
        text = text.lower().strip()
        if text in ['всё', 'все'] and bal is not None:
            return bal
        m = re.match(r'^(\d+(?:\.\d+)?)(к+)$', text)
        if m:
            n, k = float(m[1]), len(m[2])
            return int(n * [1000, 1000000, 1000000000][min(k-1, 2)])
        try:
            return int(text)
        except:
            return 0

core = BotCore()

def is_creator(uid):
    return core.admins.is_creator(uid)

def is_admin(uid):
    return core.admins.is_admin(uid)

def is_private(msg):
    return msg.chat.type == 'private'

def fmt(n):
    if n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.1f}кккк"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}ккк"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}кк"
    if n >= 1000:
        return f"{n/1000:.1f}к"
    return str(n)

async def ban_middleware(handler, event: Message, data: dict):
    if isinstance(event, Message):
        user_id = event.from_user.id
        if core.ban.is_banned(user_id) and not is_creator(user_id):
            ban_info = core.ban.get_ban_info(user_id)
            await event.reply(f"⛔ Забанен\nПричина: {ban_info['reason']}")
            return
    return await handler(event, data)

# ========== NFT Функции ==========

async def show_nft_list(message: Message or CallbackQuery, uid: str, page: int = 0):
    inventory = core.shop.inventory(uid)
    sorted_nft = sorted(inventory, key=lambda x: x.get('global_number', 0))
    items_per_page = 5
    total_pages = (len(sorted_nft) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    current_items = sorted_nft[start:end]
    
    text = f"🖼 Твои NFT\n\nСтраница {page + 1}/{total_pages}\n\n"
    
    kb = []
    for nft in current_items:
        emoji = nft.get('emoji', '🎁')
        name = nft.get('name', 'NFT')
        num = nft.get('global_number', '?')
        upgraded = "✨" if nft.get('is_upgraded') else ""
        button_text = f"{emoji} {name} #{num} {upgraded}"
        kb.append([InlineKeyboardButton(text=button_text[:50], callback_data=f"nft_view_{uid}_{nft['unique_id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"nft_page_{uid}_{page-1}"))
    if page + 1 < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"nft_page_{uid}_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_nft_detail(callback: CallbackQuery, uid: str, unique_id: str):
    inventory = core.shop.inventory(uid)
    nft = next((item for item in inventory if item['unique_id'] == unique_id), None)
    
    if not nft:
        await callback.answer("❌ NFT не найден", show_alert=True)
        return
    
    emoji = nft.get('emoji', '🎁')
    name = nft.get('name', 'NFT')
    num = nft.get('global_number', '?')
    desc = nft.get('description', 'Нет описания')
    upgraded = nft.get('is_upgraded', False)
    upgrade_info = f"\n✨ Улучшен: {nft.get('upgraded_at', 'неизвестно')[:10]}" if upgraded else ""
    purchase_date = nft.get('purchased_at', 'неизвестно')[:10]
    
    text = f"{emoji} {name} #{num}\n\n"
    text += f"📝 {desc}\n"
    text += f"📅 Куплен: {purchase_date}{upgrade_info}\n"
    text += f"🆔 {unique_id[:16]}..."
    
    kb = [
        [InlineKeyboardButton(text="💰 Продать", callback_data=f"nft_sell_{uid}_{unique_id}")],
        [InlineKeyboardButton(text="🔄 Передать", callback_data=f"nft_transfer_start_{uid}_{unique_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"nft_back_{uid}")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_shop_list(user_id, message: Message or CallbackQuery, page: int = 0):
    items = core.shop.items()
    items_list = list(items.items())
    items_per_page = 5
    total_pages = (len(items_list) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    current_items = items_list[start:end]
    
    text = f"🏪 Магазин NFT\n\nСтраница {page + 1}/{total_pages}\n\n"
    
    kb = []
    for item_id, item in current_items:
        emoji = item.get('emoji', '🎁')
        name = item.get('name', 'NFT')
        price = fmt(item.get('price', 0))
        quantity = item.get('quantity', 0)
        button_text = f"{emoji} {name} - {price} (ост. {quantity})"
        kb.append([InlineKeyboardButton(text=button_text[:50], callback_data=f"shop_view_{item_id}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"shop_page_{page-1}"))
    if page + 1 < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"shop_page_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_shop_item(callback: CallbackQuery, item_id: str):
    items = core.shop.items()
    item = items.get(item_id)
    
    if not item:
        await callback.answer("❌ Товар не найден", show_alert=True)
        await show_shop_list(callback.from_user.id, callback, 0)
        return
    
    emoji = item.get('emoji', '🎁')
    name = item.get('name', 'NFT')
    price = item.get('price', 0)
    quantity = item.get('quantity', 0)
    sold = item.get('sold', 0)
    desc = item.get('description', 'Нет описания')
    
    user_balance = core.db.get(callback.from_user.id)['balance']
    
    text = f"{emoji} {name}\n\n"
    text += f"📝 {desc}\n"
    text += f"💰 Цена: {fmt(price)}\n"
    text += f"📦 Осталось: {quantity} шт | 📊 Продано: {sold}\n\n"
    text += f"💳 Твой баланс: {fmt(user_balance)}"
    
    kb = []
    if quantity > 0 and user_balance >= price:
        kb.append([InlineKeyboardButton(text="💳 Купить", callback_data=f"shop_buy_{item_id}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="shop_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_market_list(user_id, message: Message or CallbackQuery, page: int = 0):
    listings, total = core.market.get_listings(page, 5)
    
    if not listings:
        text = "🏪 Рынок NFT\n\n📭 Пока пусто"
        kb = [[InlineKeyboardButton(text="🔄 Обновить", callback_data="market_refresh")]]
    else:
        text = f"🏪 Рынок NFT\n\nСтраница {page + 1}/{(total + 4) // 5}\n\n"
        kb = []
        
        for listing in listings:
            nft = listing['nft']
            try:
                seller_chat = await message.bot.get_chat(listing['seller_id'])
                seller_name = seller_chat.first_name
            except:
                seller_name = f"ID {listing['seller_id']}"
            
            emoji = nft.get('emoji', '🎁')
            name = nft.get('name', 'NFT')
            num = nft.get('global_number', '?')
            button_text = f"{emoji} {name} #{num} - {fmt(listing['price'])} (ID: {listing['id']})"
            if len(button_text) > 50:
                button_text = button_text[:47] + "..."
            kb.append([InlineKeyboardButton(text=button_text, callback_data=f"market_view_{listing['id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"market_page_{page-1}"))
    if (page + 1) * 5 < total:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"market_page_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    kb.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="market_refresh")])
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_market_listing(callback: CallbackQuery, listing_id: int):
    listing = core.market.get_listing(listing_id)
    if not listing:
        await callback.answer("❌ Не найдено", show_alert=True)
        await show_market_list(callback.from_user.id, callback, 0)
        return
    
    nft = listing['nft']
    
    try:
        seller_chat = await callback.bot.get_chat(listing['seller_id'])
        seller_name = seller_chat.first_name
    except:
        seller_name = f"ID {listing['seller_id']}"
    
    emoji = nft.get('emoji', '🎁')
    name = nft.get('name', 'NFT')
    num = nft.get('global_number', '?')
    desc = nft.get('description', 'Нет описания')
    
    text = f"{emoji} {name} #{num}\n\n"
    text += f"📝 {desc}\n"
    text += f"👤 Продавец: {seller_name}\n"
    text += f"💰 Цена: {fmt(listing['price'])}\n"
    text += f"📅 Выставлен: {listing['listed_at'][:10]}\n"
    text += f"🆔 ID: {listing['id']}\n\n"
    text += f"💳 Твой баланс: {fmt(core.db.get(callback.from_user.id)['balance'])}"
    
    kb = [
        [InlineKeyboardButton(text="💳 Купить", callback_data=f"market_buy_{listing_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")]
    ]
    
    if listing['seller_id'] == callback.from_user.id:
        kb.insert(0, [InlineKeyboardButton(text="❌ Снять", callback_data=f"market_cancel_{listing_id}")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_nft_for_transfer(message: Message or CallbackQuery, state: FSMContext, uid: str, page: int = 0):
    inventory = core.shop.inventory(uid)
    sorted_nft = sorted(inventory, key=lambda x: x.get('global_number', 0))
    items_per_page = 5
    total_pages = (len(sorted_nft) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    current_items = sorted_nft[start:end]
    
    text = f"🔄 Выбери NFT для передачи\n\nСтраница {page + 1}/{total_pages}\n\n"
    
    kb = []
    for nft in current_items:
        emoji = nft.get('emoji', '🎁')
        name = nft.get('name', 'NFT')
        num = nft.get('global_number', '?')
        upgraded = "✨" if nft.get('is_upgraded') else ""
        button_text = f"{emoji} {name} #{num} {upgraded}"
        kb.append([InlineKeyboardButton(text=button_text[:50], callback_data=f"transfer_select_{uid}_{nft['unique_id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"transfer_page_{uid}_{page-1}"))
    if page + 1 < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"transfer_page_{uid}_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="transfer_cancel")])
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ========== Команды ==========

async def cmd_start(event: Message or CallbackQuery):
    """Обрабатывает /start и возврат в главное меню"""
    # Получаем пользователя в зависимости от типа события
    if isinstance(event, Message):
        user_id = event.from_user.id
        chat_id = event.chat.id
        reply_method = event.reply
    else:  # CallbackQuery
        user_id = event.from_user.id
        chat_id = event.message.chat.id
        reply_method = event.message.edit_text
    
    core.db.get(user_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Игры", callback_data="menu_games"),
         InlineKeyboardButton(text="🏦 Банк", callback_data="menu_bank")],
        [InlineKeyboardButton(text="🖼️ NFT", callback_data="menu_nft"),
         InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="📋 Заработать", callback_data="menu_earn"),
         InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")]
    ])
    
    user = core.db.get(user_id)
    statuses = core.status.all()
    status = statuses.get(user['status'], statuses['novice'])
    
    # Пытаемся получить имя пользователя
    try:
        if isinstance(event, Message):
            user_name = event.from_user.first_name
        else:
            user_name = event.from_user.first_name
    except:
        user_name = "Игрок"
    
    text = f"{status['emoji']} {user_name}\n💰 Баланс: {fmt(user['balance'])}\n🎮 {user.get('games_played', 0)} игр | 🏆 {user.get('wins', 0)} побед"
    
    await reply_method(text, reply_markup=kb)

async def cmd_profile(msg):
    uid = str(msg.from_user.id)
    user = core.db.get(uid)
    statuses = core.status.all()
    status = statuses.get(user['status'], statuses['novice'])
    
    games = user.get('games_played', 0)
    wins = user.get('wins', 0)
    inventory = core.shop.inventory(uid)
    bank = core.bank.get(uid)
    
    win_rate = (wins / games * 100) if games > 0 else 0
    losses = games - wins
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="profile_bonus"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="profile_top")],
        [InlineKeyboardButton(text="💎 Общий баланс", callback_data="profile_total"),
         InlineKeyboardButton(text="💳 Банк", callback_data="bank_menu")],
        [InlineKeyboardButton(text="🖼 NFT", callback_data="nft_my"),
         InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    text = (
        f"✨ <b>ПРОФИЛЬ ИГРОКА</b> ✨\n\n"
        f"{status['emoji']} <b>{status['name']}</b>\n"
        f"┌─────────────────────┐\n"
        f"│ 🆔 <code>{uid}</code>\n"
        f"│ 👤 {msg.from_user.full_name}\n"
        f"├─────────────────────┤\n"
        f"│ 💵 Наличные: {fmt(user['balance'])}\n"
        f"│ 💳 На карте: {fmt(bank['card_balance'])}\n"
        f"│ 💎 Всего: {fmt(user['balance'] + bank['card_balance'])}\n"
        f"├─────────────────────┤\n"
        f"│ 🏆 Побед: {wins}\n"
        f"│ ❌ Поражений: {losses}\n"
        f"│ 📈 Всего игр: {games}\n"
        f"│ ⭐ Винрейт: {win_rate:.1f}%\n"
        f"├─────────────────────┤\n"
        f"│ 🎨 NFT: {len(inventory)} шт.\n"
        f"│ 📊 Кредитный рейтинг: {bank['credit_history']}/1000\n"
        f"└─────────────────────┘"
    )
    
    await msg.reply(text, reply_markup=kb, parse_mode="HTML")

async def cmd_balance(msg):
    user = core.db.get(msg.from_user.id)
    await msg.reply(f"💰 Баланс {fmt(user['balance'])}")

async def cmd_bonus(msg):
    res = core.status.get_bonus(msg.from_user.id, core.db)
    await msg.reply(res['msg'])

async def cmd_top(msg):
    top = core.db.top(limit=15)
    
    if not top:
        await msg.reply("📊 Пусто")
        return
    
    text = "🏆 Топ игроков\n\n"
    
    for i, (uid, u) in enumerate(top, 1):
        try:
            chat = await msg.bot.get_chat(int(uid))
            name = chat.first_name
        except:
            name = f"ID {uid[-4:]}"
        
        balance = u.get('balance', 0)
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name} — {fmt(balance)}\n"
    
    await msg.reply(text)

async def cmd_status(msg):
    user = core.db.get(msg.from_user.id)
    statuses = core.status.all()
    status = statuses.get(user['status'], statuses['novice'])
    
    last_bonus = user.get('last_bonus')
    bonus_info = "Никогда"
    if last_bonus:
        try:
            last_time = datetime.datetime.fromisoformat(last_bonus)
            hours_passed = (datetime.datetime.now() - last_time).total_seconds() / 3600
            if hours_passed < 1:
                next_bonus = int((1 - hours_passed) * 60)
                bonus_info = f"Через {next_bonus} мин"
            else:
                bonus_info = "Можно"
        except:
            bonus_info = "Можно"
    
    await msg.reply(
        f"{status['emoji']} {status['name']}\n\n"
        f"💰 {fmt(status['min_bonus'])} - {fmt(status['max_bonus'])}\n"
        f"⏰ {bonus_info}"
    )

async def cmd_bank(msg):
    if not is_private(msg):
        await msg.reply("❌ Банк только в личке")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Карта", callback_data="bank_card"),
         InlineKeyboardButton(text="📈 Вклады", callback_data="bank_deposits")],
        [InlineKeyboardButton(text="📉 Кредиты", callback_data="bank_loans"),
         InlineKeyboardButton(text="❓ Помощь", callback_data="bank_help")]
    ])
    await msg.reply(core.bank.menu(msg.from_user.id), reply_markup=kb)

async def cmd_card(msg):
    if not is_private(msg):
        await msg.reply("❌ Банк только в личке")
        return
    await msg.reply(f"💳 {fmt(core.bank.get(msg.from_user.id)['card_balance'])}")

async def cmd_deposit(msg, command):
    if not is_private(msg):
        return
    args = command.args.split() if command.args else []
    if len(args) != 1:
        await msg.reply("❌ положить [сумма]")
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0], u['balance'])
    if a <= 0:
        await msg.reply("❌ Неверная сумма")
        return
    res = core.bank.card_deposit(msg.from_user.id, a, u['balance'])
    if res['ok']:
        core.db.update(msg.from_user.id, balance=u['balance'] - a)
    await msg.reply(res['msg'])

async def cmd_withdraw(msg, command):
    if not is_private(msg):
        return
    args = command.args.split() if command.args else []
    if len(args) != 1:
        await msg.reply("❌ снять [сумма]")
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0])
    if a <= 0:
        await msg.reply("❌ Неверная сумма")
        return
    res = core.bank.card_withdraw(msg.from_user.id, a, u['balance'])
    if res['ok']:
        core.db.update(msg.from_user.id, balance=u['balance'] + a)
    await msg.reply(res['msg'])

async def cmd_create_deposit(msg, command):
    if not is_private(msg):
        return
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await msg.reply("❌ вклад [сумма] [дни]\n7,14,30,90,180,365")
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0], u['balance'])
    try:
        d = int(args[1])
    except:
        await msg.reply("❌ Неверный срок")
        return
    if a <= 0:
        await msg.reply("❌ Неверная сумма")
        return
    res = core.bank.create_deposit(msg.from_user.id, a, d, u['balance'])
    if res['ok']:
        core.db.update(msg.from_user.id, balance=u['balance'] - a)
    await msg.reply(res['msg'])

async def cmd_deposits(msg):
    if not is_private(msg):
        return
    b = core.bank.get(msg.from_user.id)
    active = [d for d in b['deposits'] if d['status'] == 'active']
    if not active:
        await msg.reply("📭 Нет вкладов")
        return
    text = "📈 Вклады\n\n"
    kb = []
    for d in active:
        end = datetime.datetime.fromisoformat(d['end_date'])
        left = (end - datetime.datetime.now()).days
        text += f"{d['id'][-8:]}\n💰 {fmt(d['amount'])} | 📈 {d['rate']}%\n⏰ {left} дн.\n\n"
        kb.append([InlineKeyboardButton(text=f"❌ Закрыть {d['id'][-8:]}", callback_data=f"close_deposit_{d['id']}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_create_loan(msg, command):
    if not is_private(msg):
        return
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await msg.reply("❌ кредит [сумма] [дни]\n7,14,30,90,180,365")
        return
    
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0])
    try:
        d = int(args[1])
    except:
        await msg.reply("❌ Неверный срок")
        return
    
    if a <= 0:
        await msg.reply("❌ Неверная сумма")
        return
    
    res = core.bank.create_loan(msg.from_user.id, a, d, u['balance'])
    if res['ok']:
        core.db.update(msg.from_user.id, balance=u['balance'] + a)
    await msg.reply(res['msg'])

async def cmd_loans(msg):
    if not is_private(msg):
        return
    b = core.bank.get(msg.from_user.id)
    active = [l for l in b['loans'] if l['status'] == 'active']
    if not active:
        await msg.reply("📭 Нет кредитов")
        return
    text = "📉 Кредиты\n\n"
    kb = []
    for l in active:
        end = datetime.datetime.fromisoformat(l['end_date'])
        left = (end - datetime.datetime.now()).days
        percent = int((l['total_to_return'] - l['amount']) / l['amount'] * 100)
        
        text += f"{l['id'][-8:]}\n"
        text += f"💰 {fmt(l['amount'])} | 📈 {percent}%\n"
        text += f"💵 Осталось {fmt(l['remaining'])} | ⏰ {left} дн.\n\n"
        
        kb.append([InlineKeyboardButton(
            text=f"💸 Оплатить {fmt(l['remaining'])}",
            callback_data=f"pay_loan_{l['id']}"
        )])
    
    kb.append([InlineKeyboardButton(text="💰 Новый кредит", callback_data="bank_new_loan")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
    
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_create_promo(msg: Message, state: FSMContext):
    u = core.db.get(msg.from_user.id)
    min_cost = MIN_PROMO_REWARD * MIN_PROMO_LIMIT
    
    if is_admin(msg.from_user.id):
        await state.set_state(PromoStates.waiting_reward)
        await state.update_data(step='reward')
        await msg.reply(
            f"🎫 Создание промо\n\n"
            f"💰 Награда: {fmt(MIN_PROMO_REWARD)}-{fmt(MAX_PROMO_REWARD)}\n"
            f"👥 Лимит: {MIN_PROMO_LIMIT}-{MAX_PROMO_LIMIT}\n\n"
            f"Награда:"
        )
    else:
        if u['balance'] < min_cost:
            await msg.reply(f"❌ Нужно минимум {fmt(min_cost)}")
            return
        
        await state.set_state(PromoStates.waiting_reward)
        await state.update_data(step='reward')
        await msg.reply(
            f"🎫 Создание промо\n\n"
            f"💰 Награда: {fmt(MIN_PROMO_REWARD)}-{fmt(MAX_PROMO_REWARD)}\n"
            f"👥 Лимит: {MIN_PROMO_LIMIT}-{MAX_PROMO_LIMIT}\n"
            f"💎 Спишется: награда × лимит\n\n"
            f"Награда:"
        )

async def process_promo(msg: Message, state: FSMContext):
    data = await state.get_data()
    step = data.get('step')
    
    if step == 'reward':
        a = core.parse_bet(msg.text)
        if a < MIN_PROMO_REWARD or a > MAX_PROMO_REWARD:
            await msg.reply(f"❌ От {fmt(MIN_PROMO_REWARD)} до {fmt(MAX_PROMO_REWARD)}")
            return
        await state.update_data(reward=a, step='limit')
        await msg.reply(f"💰 {fmt(a)}\n\nЛимит (от {MIN_PROMO_LIMIT} до {MAX_PROMO_LIMIT}):")
    
    elif step == 'limit':
        try:
            limit = int(msg.text.strip())
        except ValueError:
            await msg.reply(f"❌ Число от {MIN_PROMO_LIMIT} до {MAX_PROMO_LIMIT}")
            return
        
        if limit < MIN_PROMO_LIMIT or limit > MAX_PROMO_LIMIT:
            await msg.reply(f"❌ От {MIN_PROMO_LIMIT} до {MAX_PROMO_LIMIT}")
            return
        
        d = await state.get_data()
        total = d['reward'] * limit
        u = core.db.get(msg.from_user.id)
        
        is_admin_user = is_admin(msg.from_user.id)
        
        if not is_admin_user:
            if u['balance'] < total:
                await msg.reply(f"❌ Нужно {fmt(total)}")
                await state.clear()
                return
            core.db.update(msg.from_user.id, balance=u['balance'] - total)
        
        res = core.promo.create(d['reward'], msg.from_user.id, limit)
        
        if res['ok']:
            if 'created_promocodes' not in u:
                u['created_promocodes'] = []
            u['created_promocodes'].append(res['code'])
            core.db.update(msg.from_user.id, created_promocodes=u['created_promocodes'])
            
            admin_note = " (бесплатно)" if is_admin_user else ""
            await msg.reply(
                f"✅ Готово{admin_note}\n\n"
                f"🎫 {res['code']}\n"
                f"💰 {fmt(d['reward'])}\n"
                f"👥 {limit}\n"
                f"💎 {fmt(total)}"
            )
            
            core.logs.add_log(
                admin_id=msg.from_user.id if is_admin_user else None,
                action="create_promo",
                details=f"Код: {res['code']} | Награда: {fmt(d['reward'])} | Лимит: {limit}"
            )
        else:
            if not is_admin_user:
                core.db.update(msg.from_user.id, balance=u['balance'])
            await msg.reply(res['msg'])
        
        await state.clear()

async def cmd_cancel_promo(msg: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state and current_state.startswith('PromoStates'):
        await state.clear()
        await msg.reply("❌ Отменено")
    else:
        await msg.reply("❌ Нет активного создания")

async def cmd_my_promos(msg):
    u = core.db.get(msg.from_user.id)
    promos, used, claimed = core.promo.my_promos(msg.from_user.id)
    if not promos:
        await msg.reply("📭 Нет промо")
        return
    text = f"🎫 Твои промо\n\n📊 Всего: {len(promos)}\nИспользовано: {used}\nВыплачено: {fmt(claimed)}\n\n"
    for p in promos:
        exp = datetime.datetime.fromisoformat(p['expires'])
        days = (exp - datetime.datetime.now()).days
        text += f"🎫 {p['code']}\n   • {fmt(p['reward'])} | {p['used']}/{p['limit']}\n   • Осталось {p['remaining']} | {days} дн.\n\n"
    await msg.reply(text)

async def cmd_promo(msg, command):
    if not command.args:
        await msg.reply("❌ промо [код]")
        return
    res = core.promo.use(command.args.upper().strip(), msg.from_user.id, core.db)
    await msg.reply(res['msg'])

# ========== NFT Команды ==========

async def cmd_my_nft(msg: Message):
    if not is_private(msg):
        await msg.reply("❌ Только в личке")
        return
    
    uid = str(msg.from_user.id)
    inventory = core.shop.inventory(uid)
    
    if not inventory:
        await msg.reply("📭 У тебя нет NFT")
        return
    
    await show_nft_list(msg, uid, 0)

async def cmd_nft_shop(msg: Message):
    if not is_private(msg):
        await msg.reply("❌ Только в личке")
        return
    
    await show_shop_list(msg.from_user.id, msg, 0)

async def cmd_market(msg: Message):
    if not is_private(msg):
        await msg.reply("❌ Только в личке")
        return
    
    await show_market_list(msg.from_user.id, msg, 0)

async def cmd_transfer_nft_start(msg: Message, state: FSMContext):
    if not is_private(msg):
        await msg.reply("❌ Только в личке")
        return
    
    args = msg.text.split()
    if len(args) > 1:
        target = args[1].strip()
        
        try:
            user_id = int(target)
            try:
                chat = await msg.bot.get_chat(user_id)
                await state.update_data(
                    target_id=user_id,
                    target_name=chat.first_name,
                    target_uid=str(user_id)
                )
            except:
                await msg.reply("❌ Пользователь не найден")
                return
        except ValueError:
            await msg.reply("❌ Неверный ID")
            return
        
        uid = str(msg.from_user.id)
        inventory = core.shop.inventory(uid)
        
        if not inventory:
            await msg.reply("📭 У тебя нет NFT")
            await state.clear()
            return
        
        await state.set_state(TransferNFTStates.waiting_nft)
        await show_nft_for_transfer(msg, state, uid, 0)
    else:
        await state.set_state(TransferNFTStates.waiting_user)
        await msg.reply("👤 Введи ID пользователя:")

async def handle_transfer_user_input(msg: Message, state: FSMContext):
    target = msg.text.strip()
    
    try:
        user_id = int(target)
        try:
            chat = await msg.bot.get_chat(user_id)
            
            data = await state.get_data()
            unique_id = data.get('transfer_nft_id')
            
            if not unique_id:
                await msg.reply("❌ Ошибка")
                await state.clear()
                return
            
            uid = str(msg.from_user.id)
            inventory = core.shop.inventory(uid)
            nft = next((item for item in inventory if item['unique_id'] == unique_id), None)
            
            if not nft:
                await msg.reply("❌ NFT не найден")
                await state.clear()
                return
            
            if uid == str(user_id):
                await msg.reply("❌ Себе нельзя")
                await state.clear()
                return
            
            await state.update_data(
                target_id=user_id,
                target_name=chat.first_name,
                target_uid=str(user_id),
                transfer_nft_id=unique_id
            )
            
            emoji = nft.get('emoji', '🎁')
            name = nft.get('name', 'NFT')
            num = nft.get('global_number', '?')
            
            text = f"❓ Передать?\n\n"
            text += f"{emoji} {name} #{num}\n"
            text += f"Кому: {chat.first_name} (ID: {user_id})\n\n"
            text += "Всё верно?"
            
            kb = [
                [InlineKeyboardButton(text="✅ Да", callback_data=f"transfer_confirm_{user_id}_{unique_id}")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="transfer_cancel")]
            ]
            
            await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
            
        except Exception as e:
            await msg.reply(f"❌ Пользователь не найден")
            return
    except ValueError:
        await msg.reply("❌ Неверный ID")
        return

async def process_transfer_nft(callback: CallbackQuery, state: FSMContext, uid: str, unique_id: str):
    data = await state.get_data()
    target_id = data.get('target_id')
    target_name = data.get('target_name', f"ID {target_id}")
    
    if not target_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()
        return
    
    if uid == str(target_id):
        await callback.answer("❌ Себе нельзя", show_alert=True)
        await state.clear()
        return
    
    inventory = core.shop.inventory(uid)
    nft = next((item for item in inventory if item['unique_id'] == unique_id), None)
    
    if not nft:
        await callback.answer("❌ NFT не найден", show_alert=True)
        await state.clear()
        return
    
    emoji = nft.get('emoji', '🎁')
    name = nft.get('name', 'NFT')
    num = nft.get('global_number', '?')
    
    text = f"❓ Передать?\n\n"
    text += f"{emoji} {name} #{num}\n"
    text += f"Кому: {target_name} (ID: {target_id})\n\n"
    text += "Всё верно?"
    
    kb = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"transfer_confirm_{target_id}_{unique_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="transfer_cancel")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def confirm_transfer_nft(callback: CallbackQuery, state: FSMContext, to_uid: str, unique_id: str):
    from_uid = str(callback.from_user.id)
    
    inventory = core.shop.inventory(from_uid)
    nft_exists = any(item['unique_id'] == unique_id for item in inventory)
    
    if not nft_exists:
        await callback.answer("❌ NFT уже нет", show_alert=True)
        await state.clear()
        return
    
    res = core.shop.transfer_nft(from_uid, to_uid, unique_id)
    
    if res['ok']:
        await callback.answer("✅ NFT передан", show_alert=True)
        await callback.message.edit_text(f"✅ NFT передан пользователю ID: {to_uid}")
        
        try:
            nft = res['nft']
            emoji = nft.get('emoji', '🎁')
            name = nft.get('name', 'NFT')
            num = nft.get('global_number', '?')
            
            await callback.bot.send_message(
                int(to_uid),
                f"🎁 Тебе передали NFT!\n\n{emoji} {name} #{num}\nОт: {callback.from_user.full_name}"
            )
        except:
            pass
    else:
        await callback.answer(res['msg'], show_alert=True)
    
    await state.clear()

async def cmd_create_nft(msg: Message, state: FSMContext):
    if not is_creator(msg.from_user.id):
        return
    
    await state.set_state(AdminStates.waiting_nft_id)
    await msg.reply(
        "🖼 Создание NFT\n\n"
        "ID товара (английские буквы, без пробелов):\n"
        "например: golden_pepe"
    )

async def process_nft_id(msg: Message, state: FSMContext):
    nft_id = msg.text.strip()
    
    if not re.match(r'^[a-zA-Z0-9_]+$', nft_id):
        await msg.reply("❌ Только буквы, цифры и _")
        return
    
    items = core.shop.items()
    if nft_id in items:
        await msg.reply("❌ Уже есть")
        return
    
    await state.update_data(nft_id=nft_id)
    await state.set_state(AdminStates.waiting_nft_name)
    await msg.reply("✅ ID принят\n\nНазвание:")

async def process_nft_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    
    if len(name) > 50:
        await msg.reply("❌ Максимум 50 символов")
        return
    
    await state.update_data(nft_name=name)
    await state.set_state(AdminStates.waiting_nft_price)
    await msg.reply("✅ Название принято\n\nЦена (1к, 1кк и т.д.):")

async def process_nft_price(msg: Message, state: FSMContext):
    price = core.parse_bet(msg.text)
    
    if price <= 0:
        await msg.reply("❌ Цена > 0")
        return
    
    if price > 1000000000000:
        await msg.reply("❌ Максимум 1кккк")
        return
    
    await state.update_data(nft_price=price)
    await state.set_state(AdminStates.waiting_nft_quantity)
    await msg.reply(f"✅ Цена: {fmt(price)}\n\nКоличество (0-10000):")

async def process_nft_quantity(msg: Message, state: FSMContext):
    try:
        quantity = int(msg.text.strip())
        if quantity < 0:
            await msg.reply("❌ Не может быть отрицательным")
            return
        if quantity > 10000:
            await msg.reply("❌ Максимум 10000")
            return
    except ValueError:
        await msg.reply("❌ Введи число")
        return
    
    await state.update_data(nft_quantity=quantity)
    await state.set_state(AdminStates.waiting_nft_description)
    await msg.reply("✅ Количество принято\n\nОписание (или `-` если нет):")

async def process_nft_description(msg: Message, state: FSMContext):
    description = msg.text.strip()
    
    if description == '-':
        description = "Нет описания"
    
    if len(description) > 200:
        await msg.reply("❌ Максимум 200 символов")
        return
    
    await state.update_data(nft_description=description)
    await state.set_state(AdminStates.waiting_nft_emoji)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁", callback_data="emoji_🎁"),
         InlineKeyboardButton(text="💎", callback_data="emoji_💎"),
         InlineKeyboardButton(text="👑", callback_data="emoji_👑")],
        [InlineKeyboardButton(text="⚡", callback_data="emoji_⚡"),
         InlineKeyboardButton(text="🔥", callback_data="emoji_🔥"),
         InlineKeyboardButton(text="⭐", callback_data="emoji_⭐")],
        [InlineKeyboardButton(text="🎮", callback_data="emoji_🎮"),
         InlineKeyboardButton(text="💰", callback_data="emoji_💰"),
         InlineKeyboardButton(text="💊", callback_data="emoji_💊")],
        [InlineKeyboardButton(text="🖼 Свой", callback_data="emoji_custom")]
    ])
    
    await msg.reply("✅ Описание принято\n\nЭмодзи:", reply_markup=kb)

async def process_nft_emoji(msg: Message, state: FSMContext):
    emoji = msg.text.strip()
    
    if len(emoji) > 10:
        await msg.reply("❌ Это не эмодзи")
        return
    
    await finish_nft_creation(msg, state, emoji)

async def finish_nft_creation(msg: Message, state: FSMContext, emoji: str):
    data = await state.get_data()
    
    nft_id = data.get('nft_id')
    name = data.get('nft_name')
    price = data.get('nft_price')
    quantity = data.get('nft_quantity')
    description = data.get('nft_description')
    
    success = core.shop.add(nft_id, name, price, quantity, description, emoji)
    
    if success:
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="create_nft",
            details=f"{nft_id} | {name} | {fmt(price)} | {quantity}"
        )
        
        await msg.reply(
            f"✅ NFT создан\n\n"
            f"🆔 {nft_id}\n"
            f"{emoji} {name}\n"
            f"💰 {fmt(price)}\n"
            f"📦 {quantity}\n"
            f"📝 {description}"
        )
    else:
        await msg.reply(f"❌ Ошибка, ID {nft_id} уже есть")
    
    await state.clear()

async def cmd_all_nft(msg: Message):
    if not is_creator(msg.from_user.id):
        return
    
    items = core.shop.items()
    
    if not items:
        await msg.reply("📭 Нет NFT")
        return
    
    text = "🖼 Все NFT\n\n"
    
    for item_id, item in items.items():
        emoji = item.get('emoji', '🎁')
        name = item.get('name', 'Без названия')
        price = item.get('price', 0)
        quantity = item.get('quantity', 0)
        sold = item.get('sold', 0)
        
        text += f"{emoji} {name}\n"
        text += f"   🆔 {item_id}\n"
        text += f"   💰 {fmt(price)} | 📦 {quantity} | 📊 {sold}\n\n"
    
    await msg.reply(text)

# ========== Игровые команды ==========

async def cmd_games(msg):
    await msg.reply(
        "Игры:\n"
        "🪙 монетка - орёл/решка (x2)\n"
        "🎲 кубик - число 1-6 (x6)\n"
        "🎰 слоты - до x10\n"
        "💣 мины - не наступи на мину\n"
        "🏗️ башня - лезь наверх\n"
        "💎 алмазы - ищи алмазы\n"
        "🔺 пирамида - ищи двери (по умолчанию 3)\n"
        "🚀 краш - забери до взрыва\n"
        "⚽ футбол - забей гол\n"
        "🏀 баскетбол - забрось мяч\n"
        "🎯 дартс - брось дротик\n"
        "🐸 квак - 4 ряда с возрастающими минами\n"
        "🪨 кнб - камень/ножницы/бумага\n"
        "⚔️ дуэль кнб - сразись с игроком"
    )

async def cmd_cancel_game(msg: Message):
    uid = msg.from_user.id
    chat_id = msg.chat.id
    cancelled = False
    msg_text = ""
    
    if uid in core.crash.games:
        res = core.crash.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.mines.games:
        res = core.mines.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.tower.games:
        res = core.tower.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.diamonds.games:
        res = core.diamonds.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.pyramid.games:
        res = core.pyramid.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.gold.games:
        res = core.gold.cancel_game(uid, chat_id)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.risk.games:
        res = core.risk.cancel_game(uid, chat_id)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.quack.games:
        res = core.quack.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if cancelled:
        await msg.reply(msg_text.strip())
    else:
        await msg.reply("❌ Нет активной игры")

async def cmd_id(msg: Message):
    if not msg.reply_to_message:
        await msg.reply("❌ Ответь на сообщение")
        return
    
    target_user = msg.reply_to_message.from_user
    await msg.reply(f"🆔 <code>{target_user.id}</code>", parse_mode="HTML")

async def cmd_admins(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    admins = core.admins.get_all_admins()
    
    if not admins:
        await msg.reply("📭 Нет админов")
        return
    
    text = "👑 Админы\n\n"
    
    for uid, info in admins.items():
        try:
            chat = await msg.bot.get_chat(int(uid))
            name = chat.first_name
        except:
            name = f"ID {uid}"
        
        role = "👑" if info.get("is_creator") else "🛡️"
        added_at = info.get('added_at', '')[:10]
        
        text += f"{role} {name}\n"
        text += f"   🆔 {uid}\n"
        text += f"   📅 с {added_at}\n\n"
    
    await msg.reply(text)

async def cmd_make_admin(msg: Message):
    if not is_creator(msg.from_user.id):
        return
    
    if not msg.reply_to_message:
        await msg.reply("❌ Ответь на сообщение")
        return
    
    target_id = msg.reply_to_message.from_user.id
    
    res = core.admins.add_admin(target_id, msg.from_user.id)
    
    if res['ok']:
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="make_admin",
            target_id=target_id
        )
        
        await msg.reply(res['msg'])
        try:
            await msg.bot.send_message(target_id, f"👑 Ты админ")
        except:
            pass
    else:
        await msg.reply(res['msg'])

async def cmd_remove_admin(msg: Message):
    if not is_creator(msg.from_user.id):
        return
    
    if not msg.reply_to_message:
        await msg.reply("❌ Ответь на сообщение")
        return
    
    target_id = msg.reply_to_message.from_user.id
    
    res = core.admins.remove_admin(target_id, msg.from_user.id)
    
    if res['ok']:
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="remove_admin",
            target_id=target_id
        )
        
        await msg.reply(res['msg'])
        try:
            await msg.bot.send_message(target_id, f"👋 Больше не админ")
        except:
            pass
    else:
        await msg.reply(res['msg'])

async def cmd_block(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    
    target_id = None
    reason = ""
    
    parts = msg.text.split(maxsplit=2)
    if len(parts) >= 2:
        try:
            target_id = int(parts[1])
            if len(parts) >= 3:
                reason = parts[2]
        except ValueError:
            if msg.reply_to_message:
                target_id = msg.reply_to_message.from_user.id
                reason = parts[1] if len(parts) >= 2 else ""
    
    if not target_id and msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
        if len(parts) >= 2:
            reason = parts[1]
    
    if not target_id:
        await msg.reply("❌ блок [ID] [причина] или блок [причина] (ответом)")
        return
    
    if is_creator(target_id):
        await msg.reply("❌ Нельзя заблокировать создателя")
        return
    
    try:
        user_chat = await msg.bot.get_chat(target_id)
        target_name = user_chat.full_name
    except:
        target_name = f"ID {target_id}"
    
    core.ban.ban(target_id, msg.from_user.id, reason)
    
    core.logs.add_log(
        admin_id=msg.from_user.id,
        action="ban",
        target_id=target_id,
        details=f"Причина: {reason if reason else 'Не указана'}"
    )
    
    reason_str = f" ({reason})" if reason else ""
    await msg.reply(f"⛔ {target_name} забанен{reason_str}")
    
    try:
        await msg.bot.send_message(
            target_id,
            f"⛔ Ты забанен\nПричина: {reason if reason else 'Не указана'}"
        )
    except:
        pass

async def cmd_unblock(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    target_id = None
    
    parts = msg.text.split()
    if len(parts) >= 2:
        try:
            target_id = int(parts[1])
        except ValueError:
            await msg.reply("❌ Неверный ID")
            return
    
    if not target_id and msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
    
    if not target_id:
        await msg.reply("❌ разблок [ID] или разблок (ответом)")
        return
    
    if core.ban.unban(target_id):
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="unban",
            target_id=target_id
        )
        
        await msg.reply(f"✅ Пользователь {target_id} разблокирован")
        
        try:
            await msg.bot.send_message(target_id, f"✅ Ты разблокирован")
        except:
            pass
    else:
        await msg.reply(f"❌ Пользователь {target_id} не в бане")

async def cmd_admin_give(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    parts = msg.text.lower().split()
    
    if len(parts) == 3:
        try:
            target_id = int(parts[1])
            amount = core.parse_bet(parts[2])
            
            if amount <= 0:
                await msg.reply("❌ Сумма > 0")
                return
            
            try:
                user_chat = await msg.bot.get_chat(target_id)
                target_name = user_chat.full_name
            except:
                await msg.reply(f"❌ ID {target_id} не найден")
                return
            
            u = core.db.get(target_id)
            core.db.update(target_id, balance=u['balance'] + amount)
            
            core.logs.add_log(
                admin_id=msg.from_user.id,
                action="give",
                target_id=target_id,
                amount=amount
            )
            
            await msg.reply(f"✅ {target_name} +{fmt(amount)}")
            
            try:
                await msg.bot.send_message(target_id, f"💰 +{fmt(amount)}")
            except:
                pass
            
        except ValueError:
            await msg.reply("❌ Неверный ID")
        except Exception as e:
            await msg.reply(f"❌ Ошибка")
    
    elif len(parts) == 2 and msg.reply_to_message:
        amount = core.parse_bet(parts[1])
        if amount <= 0:
            await msg.reply("❌ Сумма > 0")
            return
        
        target_id = msg.reply_to_message.from_user.id
        target_name = msg.reply_to_message.from_user.full_name
        
        u = core.db.get(target_id)
        core.db.update(target_id, balance=u['balance'] + amount)
        
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="give",
            target_id=target_id,
            amount=amount
        )
        
        await msg.reply(f"✅ {target_name} +{fmt(amount)}")
        
        try:
            await msg.bot.send_message(target_id, f"💰 +{fmt(amount)}")
        except:
            pass
    
    else:
        await msg.reply("❌ выдать [ID] [сумма] или выдать [сумма] (ответом)")

async def cmd_admin_take(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    parts = msg.text.lower().split()
    
    if len(parts) == 3:
        try:
            target_id = int(parts[1])
            amount = core.parse_bet(parts[2])
            
            if amount <= 0:
                await msg.reply("❌ Сумма > 0")
                return
            
            try:
                user_chat = await msg.bot.get_chat(target_id)
                target_name = user_chat.full_name
            except:
                await msg.reply(f"❌ ID {target_id} не найден")
                return
            
            u = core.db.get(target_id)
            if u['balance'] < amount:
                await msg.reply(f"❌ У {target_name} только {fmt(u['balance'])}")
                return
            
            core.db.update(target_id, balance=u['balance'] - amount)
            
            core.logs.add_log(
                admin_id=msg.from_user.id,
                action="take",
                target_id=target_id,
                amount=amount
            )
            
            await msg.reply(f"✅ {target_name} -{fmt(amount)}")
            
            try:
                await msg.bot.send_message(target_id, f"💸 -{fmt(amount)}")
            except:
                pass
            
        except ValueError:
            await msg.reply("❌ Неверный ID")
        except Exception as e:
            await msg.reply(f"❌ Ошибка")
    
    elif len(parts) == 2 and msg.reply_to_message:
        amount = core.parse_bet(parts[1])
        if amount <= 0:
            await msg.reply("❌ Сумма > 0")
            return
        
        target_id = msg.reply_to_message.from_user.id
        target_name = msg.reply_to_message.from_user.full_name
        
        u = core.db.get(target_id)
        if u['balance'] < amount:
            await msg.reply(f"❌ У {target_name} только {fmt(u['balance'])}")
            return
        
        core.db.update(target_id, balance=u['balance'] - amount)
        
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="take",
            target_id=target_id,
            amount=amount
        )
        
        await msg.reply(f"✅ {target_name} -{fmt(amount)}")
        
        try:
            await msg.bot.send_message(target_id, f"💸 -{fmt(amount)}")
        except:
            pass
    
    else:
        await msg.reply("❌ забрать [ID] [сумма] или забрать [сумма] (ответом)")

# ========== Рекламные задания ==========

async def cmd_ad_start(msg: Message, state: FSMContext):
    """Начать создание рекламного задания"""
    text = (
        "📢 СОЗДАНИЕ РЕКЛАМНОГО ЗАДАНИЯ\n\n"
        "Шаг 1 из 4: Укажите канал\n\n"
        "Добавьте меня (@DropPepebot) в администраторы канала "
        "и напишите username канала (например @channel)\n\n"
        "❗ Бот должен быть администратором для проверки подписки"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ad_cancel")]
    ])
    
    await msg.reply(text, reply_markup=kb)
    await state.set_state(AdStates.waiting_channel)

async def process_ad_channel(msg: Message, state: FSMContext):
    """Обрабатывает ввод канала"""
    channel_input = msg.text.strip()
    
    channel_username = channel_input.replace('@', '')
    
    try:
        try:
            chat = await msg.bot.get_chat(f"@{channel_username}")
        except:
            chat = await msg.bot.get_chat(channel_username)
        
        if chat.type not in ['channel', 'supergroup']:
            await msg.reply(
                "❌ Это не канал!\n\n"
                "Убедитесь что вы отправили username канала, а не пользователя.\n"
                "Каналы обычно имеют вид @channel_name"
            )
            return
        
        try:
            bot_member = await msg.bot.get_chat_member(chat.id, msg.bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await msg.reply(
                    f"❌ Я не администратор в канале {chat.title}!\n\n"
                    f"Добавьте меня (@DropPepebot) в администраторы канала и попробуйте снова.\n\n"
                    f"Инструкция:\n"
                    f"1. Зайдите в настройки канала\n"
                    f"2. Перейдите в раздел 'Администраторы'\n"
                    f"3. Добавьте @DropPepebot\n"
                    f"4. Выдайте права (хотя бы чтение сообщений)\n"
                    f"5. Нажмите 'Сохранить'\n"
                    f"6. Попробуйте снова"
                )
                return
        except Exception as e:
            await msg.reply(
                f"❌ Не могу проверить права бота в канале.\n\n"
                f"Убедитесь что:\n"
                f"• Канал существует\n"
                f"• Бот добавлен в администраторы\n"
                f"• У бота есть права\n\n"
                f"Попробуйте ещё раз:"
            )
            return
        
        channel_info = {
            "id": chat.id,
            "name": chat.title,
            "username": f"@{chat.username}" if chat.username else None,
            "url": f"https://t.me/{chat.username}" if chat.username else None
        }
        
        await state.update_data(channel_info=channel_info)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="5 👥", callback_data="ad_subs_5"),
             InlineKeyboardButton(text="10 👥", callback_data="ad_subs_10"),
             InlineKeyboardButton(text="20 👥", callback_data="ad_subs_20")],
            [InlineKeyboardButton(text="✏️ Свой вариант", callback_data="ad_subs_custom")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="ad_cancel")]
        ])
        
        await msg.reply(
            f"✅ Канал найден: {chat.title}\n\n"
            f"Шаг 2 из 4: Сколько человек должно подписаться?\n\n"
            f"Выберите количество:",
            reply_markup=kb
        )
        await state.set_state(AdStates.waiting_subscribers)
        
    except Exception as e:
        error_text = str(e)
        await msg.reply(
            f"❌ Не удалось найти канал '{channel_input}'\n\n"
            f"Возможные причины:\n"
            f"• Канал не существует\n"
            f"• Канал приватный\n"
            f"• Бот не добавлен в администраторы\n"
            f"• Неправильный username\n\n"
            f"Убедитесь что:\n"
            f"1. Канал существует и доступен\n"
            f"2. Вы добавили @DropPepebot в администраторы\n"
            f"3. Написали правильный username (например @channel)\n\n"
            f"Попробуйте снова:"
        )

async def process_ad_subs_callback(cb: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор количества подписчиков"""
    data = cb.data
    
    if data == "ad_subs_custom":
        await cb.message.edit_text(
            "✏️ Введите количество подписчиков (число от 1 до 100):"
        )
        await cb.answer()
        return
    
    elif data.startswith("ad_subs_"):
        count = int(data.split('_')[2])
        
        await state.update_data(subscribers_count=count)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="50к 💰", callback_data="ad_reward_50000"),
             InlineKeyboardButton(text="100к 💰", callback_data="ad_reward_100000"),
             InlineKeyboardButton(text="200к 💰", callback_data="ad_reward_200000")],
            [InlineKeyboardButton(text="✏️ Свой вариант", callback_data="ad_reward_custom")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="ad_cancel")]
        ])
        
        await cb.message.edit_text(
            f"✅ Выбрано: {count} подписчиков\n\n"
            f"Шаг 3 из 4: Сколько платить за одного подписчика?\n\n"
            f"Выберите сумму:",
            reply_markup=kb
        )
        await state.set_state(AdStates.waiting_reward)
        await cb.answer()

async def process_ad_subs_custom(msg: Message, state: FSMContext):
    """Обрабатывает ввод своего количества подписчиков"""
    try:
        count = int(msg.text.strip())
        
        if count < 1 or count > 100:
            await msg.reply("❌ Введите число от 1 до 100")
            return
        
        await state.update_data(subscribers_count=count)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="50к 💰", callback_data="ad_reward_50000"),
             InlineKeyboardButton(text="100к 💰", callback_data="ad_reward_100000"),
             InlineKeyboardButton(text="200к 💰", callback_data="ad_reward_200000")],
            [InlineKeyboardButton(text="✏️ Свой вариант", callback_data="ad_reward_custom")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="ad_cancel")]
        ])
        
        await msg.reply(
            f"✅ Выбрано: {count} подписчиков\n\n"
            f"Шаг 3 из 4: Сколько платить за одного подписчика?\n\n"
            f"Выберите сумму:",
            reply_markup=kb
        )
        await state.set_state(AdStates.waiting_reward)
        
    except ValueError:
        await msg.reply("❌ Введите число!")

async def process_ad_reward_callback(cb: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор награды"""
    data = cb.data
    user_id = cb.from_user.id
    user = core.db.get(user_id)
    
    if data == "ad_reward_custom":
        await cb.message.edit_text(
            "✏️ Введите сумму за одного подписчика (от 1к до 500к):"
        )
        await cb.answer()
        return
    
    elif data.startswith("ad_reward_"):
        reward = int(data.split('_')[2])
        
        data_state = await state.get_data()
        subscribers_count = data_state.get('subscribers_count')
        channel_info = data_state.get('channel_info')
        
        total_cost = reward * subscribers_count
        
        is_admin_user = is_admin(user_id)
        
        if not is_admin_user:
            if user['balance'] < total_cost:
                await cb.answer(f"❌ Не хватает денег! Нужно {fmt(total_cost)}", show_alert=True)
                return
        
        await state.update_data(reward_per_user=reward, total_cost=total_cost)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="ad_confirm"),
             InlineKeyboardButton(text="❌ Отмена", callback_data="ad_cancel")]
        ])
        
        admin_note = " (БЕСПЛАТНО)" if is_admin_user else ""
        
        await cb.message.edit_text(
            f"📢 ПОДТВЕРЖДЕНИЕ ЗАДАНИЯ\n\n"
            f"📺 Канал: {channel_info['name']}\n"
            f"👥 Подписчиков: {subscribers_count}\n"
            f"💰 Награда за подписку: {fmt(reward)}\n"
            f"💎 Общая стоимость: {fmt(total_cost)}{admin_note}\n\n"
            f"Всё верно?",
            reply_markup=kb
        )
        await state.set_state(AdStates.waiting_confirm)
        await cb.answer()

async def process_ad_reward_custom(msg: Message, state: FSMContext):
    """Обрабатывает ввод своей награды"""
    try:
        reward = core.parse_bet(msg.text)
        
        if reward < 1000 or reward > 500000:
            await msg.reply("❌ Сумма должна быть от 1к до 500к")
            return
        
        user_id = msg.from_user.id
        user = core.db.get(user_id)
        data_state = await state.get_data()
        subscribers_count = data_state.get('subscribers_count')
        channel_info = data_state.get('channel_info')
        
        total_cost = reward * subscribers_count
        is_admin_user = is_admin(user_id)
        
        if not is_admin_user:
            if user['balance'] < total_cost:
                await msg.reply(f"❌ Не хватает денег! Нужно {fmt(total_cost)}, у тебя {fmt(user['balance'])}")
                return
        
        await state.update_data(reward_per_user=reward, total_cost=total_cost)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="ad_confirm"),
             InlineKeyboardButton(text="❌ Отмена", callback_data="ad_cancel")]
        ])
        
        admin_note = " (БЕСПЛАТНО)" if is_admin_user else ""
        
        await msg.reply(
            f"📢 ПОДТВЕРЖДЕНИЕ ЗАДАНИЯ\n\n"
            f"📺 Канал: {channel_info['name']}\n"
            f"👥 Подписчиков: {subscribers_count}\n"
            f"💰 Награда за подписку: {fmt(reward)}\n"
            f"💎 Общая стоимость: {fmt(total_cost)}{admin_note}\n\n"
            f"Всё верно?",
            reply_markup=kb
        )
        await state.set_state(AdStates.waiting_confirm)
        
    except ValueError:
        await msg.reply("❌ Неверная сумма! Используй формат: 1000, 5к, 50к, 100к")

async def process_ad_confirm(cb: CallbackQuery, state: FSMContext):
    """Подтверждает создание задания"""
    data = await state.get_data()
    user_id = cb.from_user.id
    
    channel_info = data.get('channel_info')
    subscribers_count = data.get('subscribers_count')
    reward_per_user = data.get('reward_per_user')
    total_cost = data.get('total_cost')
    
    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        user = core.db.get(user_id)
        core.db.update(user_id, balance=user['balance'] - total_cost)
    
    result = core.ads.create_task(
        creator_id=user_id,
        channel_info=channel_info,
        subscribers_count=subscribers_count,
        reward_per_user=reward_per_user,
        total_cost=total_cost
    )
    
    if result['ok']:
        task = result['task']
        
        admin_note = " (бесплатно)" if is_admin_user else f" (списано {fmt(total_cost)})"
        
        await cb.message.edit_text(
            f"✅ ЗАДАНИЕ СОЗДАНО! #{task['id']}\n\n"
            f"📺 Канал: {channel_info['name']}\n"
            f"👥 Нужно подписчиков: {subscribers_count}\n"
            f"💰 Награда за подписку: {fmt(reward_per_user)}\n"
            f"💎 Твой бюджет: {fmt(total_cost)}{admin_note}\n\n"
            f"Игроки могут выполнить задание через заработать"
        )
        
        core.logs.add_log(
            admin_id=user_id if is_admin_user else None,
            action="create_ad",
            details=f"Задание #{task['id']} | {subscribers_count} чел | {fmt(reward_per_user)}"
        )
    else:
        await cb.message.edit_text(f"❌ Ошибка: {result['msg']}")
    
    await state.clear()
    await cb.answer()

async def process_ad_cancel(cb: CallbackQuery, state: FSMContext):
    """Отменяет создание задания"""
    await state.clear()
    await cb.message.edit_text("❌ Создание задания отменено")
    await cb.answer()

async def cmd_earn(msg: Message):
    """Показать доступные задания"""
    uid = msg.from_user.id
    
    tasks = core.ads.get_available_tasks(uid)
    
    if not tasks:
        await msg.reply(
            "📭 Нет доступных заданий\n\n"
            "Ты можешь создать своё задание через /реклама"
        )
        return
    
    text = "📋 ДОСТУПНЫЕ ЗАДАНИЯ\n\n"
    
    kb = []
    for task in tasks:
        remaining = task['subscribers_needed'] - task['completed_count']
        progress = f"✅ {task['completed_count']}/{task['subscribers_needed']}"
        
        text += f"#{task['id']} • {task['channel_name']}\n"
        text += f"💰 Награда: +{fmt(task['reward_per_user'])}\n"
        text += f"📊 Осталось мест: {remaining}\n\n"
        
        kb.append([InlineKeyboardButton(
            text=f"✅ Выполнить #{task['id']} (+{fmt(task['reward_per_user'])})",
            callback_data=f"do_task_{task['id']}"
        )])
    
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def process_do_task(cb: CallbackQuery, state: FSMContext):
    """Обрабатывает выполнение задания"""
    data = cb.data
    uid = cb.from_user.id
    
    if data.startswith('do_task_'):
        task_id = int(data.split('_')[2])
        task = core.ads.get_task(task_id)
        
        if not task:
            await cb.answer("❌ Задание не найдено", show_alert=True)
            return
        
        if not task['active']:
            await cb.answer("❌ Задание уже неактивно", show_alert=True)
            return
        
        if task['completed_count'] >= task['subscribers_needed']:
            await cb.answer("❌ Лимит подписчиков исчерпан", show_alert=True)
            return
        
        if uid in task['users_completed']:
            await cb.answer("❌ Ты уже выполнил это задание", show_alert=True)
            return
        
        try:
            member = await cb.bot.get_chat_member(chat_id=task['channel_id'], user_id=uid)
            is_subscribed = member.status in ['member', 'administrator', 'creator']
        except:
            is_subscribed = False
        
        if not is_subscribed:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📺 Подписаться", url=task['channel_url'])],
                [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data=f"check_sub_{task_id}")]
            ])
            
            await cb.message.edit_text(
                f"❌ Ты не подписан на канал {task['channel_name']}!\n\n"
                f"1. Нажми кнопку 'Подписаться'\n"
                f"2. Подпишись на канал\n"
                f"3. Нажми 'Проверить подписку'",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        result = core.ads.complete_task(uid, task_id)
        
        if result['ok']:
            await cb.message.edit_text(
                f"✅ ЗАДАНИЕ ВЫПОЛНЕНО!\n\n"
                f"📺 Канал: {task['channel_name']}\n"
                f"💰 Получено: +{fmt(result['reward'])}\n"
                f"📊 Прогресс задания: {result['completed']}/{result['total']}"
            )
            await cb.answer("✅ Награда зачислена!", show_alert=True)
        else:
            await cb.answer(result['msg'], show_alert=True)

async def process_check_sub(cb: CallbackQuery, state: FSMContext):
    """Проверяет подписку после того как пользователь подписался"""
    data = cb.data
    uid = cb.from_user.id
    
    if data.startswith('check_sub_'):
        task_id = int(data.split('_')[2])
        task = core.ads.get_task(task_id)
        
        if not task:
            await cb.answer("❌ Задание не найдено", show_alert=True)
            return
        
        try:
            member = await cb.bot.get_chat_member(chat_id=task['channel_id'], user_id=uid)
            is_subscribed = member.status in ['member', 'administrator', 'creator']
        except:
            is_subscribed = False
        
        if not is_subscribed:
            await cb.answer("❌ Всё ещё не подписан!", show_alert=True)
            return
        
        result = core.ads.complete_task(uid, task_id)
        
        if result['ok']:
            await cb.message.edit_text(
                f"✅ ЗАДАНИЕ ВЫПОЛНЕНО!\n\n"
                f"📺 Канал: {task['channel_name']}\n"
                f"💰 Получено: +{fmt(result['reward'])}\n"
                f"📊 Прогресс задания: {result['completed']}/{result['total']}"
            )
            await cb.answer("✅ Награда зачислена!", show_alert=True)
        else:
            await cb.answer(result['msg'], show_alert=True)

async def cmd_my_ads(msg: Message):
    """Показать созданные пользователем задания"""
    uid = msg.from_user.id
    
    tasks = core.ads.get_user_tasks(uid)
    
    if not tasks:
        await msg.reply("📭 Ты ещё не создавал заданий")
        return
    
    text = "📊 МОИ ЗАДАНИЯ\n\n"
    
    kb = []
    for task in tasks:
        status = "✅ АКТИВНО" if task['active'] else "❌ ЗАВЕРШЕНО"
        remaining = task['subscribers_needed'] - task['completed_count']
        progress = f"{task['completed_count']}/{task['subscribers_needed']}"
        
        text += f"#{task['id']} • {task['channel_name']}\n"
        text += f"📊 Статус: {status}\n"
        text += f"💰 За подписку: {fmt(task['reward_per_user'])}\n"
        text += f"📈 Прогресс: {progress}\n"
        text += f"🎯 Осталось: {remaining}\n\n"
        
        if task['active']:
            kb.append([InlineKeyboardButton(
                text=f"❌ Отключить #{task['id']}",
                callback_data=f"stop_ad_{task['id']}"
            )])
    
    if kb:
        await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await msg.reply(text)

async def process_stop_ad(cb: CallbackQuery, state: FSMContext):
    """Отключает задание"""
    data = cb.data
    uid = cb.from_user.id
    
    if data.startswith('stop_ad_'):
        task_id = int(data.split('_')[2])
        
        result = core.ads.deactivate_task(task_id, uid)
        
        await cb.answer(result['msg'], show_alert=True)
        
        if result['ok']:
            await cmd_my_ads(cb.message)

# ========== Команда проверки канала ==========

async def cmd_check_channel(msg: Message, command: CommandObject):
    """Проверяет, есть ли бот в канале (только для админов)"""
    if not is_admin(msg.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 1:
        await msg.reply("❌ проверка_канала [username]\nПример: проверка_канала @channel")
        return
    
    channel_input = args[0].strip()
    channel_username = channel_input.replace('@', '')
    
    try:
        chat = await msg.bot.get_chat(f"@{channel_username}")
        
        text = f"📊 ИНФОРМАЦИЯ О КАНАЛЕ\n\n"
        text += f"📌 Название: {chat.title}\n"
        text += f"🆔 ID: {chat.id}\n"
        text += f"📱 Username: @{chat.username}\n"
        text += f"📋 Тип: {chat.type}\n\n"
        
        try:
            bot_member = await msg.bot.get_chat_member(chat.id, msg.bot.id)
            status_map = {
                'creator': '👑 Создатель',
                'administrator': '🛡️ Администратор',
                'member': '👤 Участник',
                'left': '❌ Не в канале',
                'kicked': '🚫 Заблокирован'
            }
            status = status_map.get(bot_member.status, bot_member.status)
            text += f"🤖 Статус бота: {status}"
        except:
            text += f"🤖 Статус бота: ❌ Не удалось проверить"
        
        await msg.reply(text)
        
    except Exception as e:
        await msg.reply(f"❌ Канал не найден или недоступен")

# ========== Ивент команды ==========

async def cmd_event_start(msg: Message, command: CommandObject):
    """Запустить ивент (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 2:
        await msg.reply(
            "❌ ивент [название] [секунды]\n"
            "пример: ивент money 60\n"
            "пример: ивент crash 120"
        )
        return
    
    event_name = args[0].lower()
    try:
        duration = int(args[1])
    except:
        await msg.reply("❌ Время должно быть числом в секундах")
        return
    
    if duration < 10:
        await msg.reply("❌ Минимум 10 секунд")
        return
    
    if duration > 3600:
        await msg.reply("❌ Максимум 3600 секунд (1 час)")
        return
    
    if event_name not in ['money', 'crash']:
        await msg.reply("❌ Доступные ивенты: money, crash")
        return
    
    if core.events.active_event:
        core.events.end_event()
    
    event = core.events.create_event(event_name, duration, msg.from_user.id, msg.chat.id)
    
    if event_name == 'money':
        text = f"🎉 ИВЕНТ НАЧАЛСЯ!\n💰 x2 на {duration} сек\n⏰ Успей выиграть больше!"
    else:
        text = f"💥 КРАШ ИВЕНТ!\n📈 Минимальный множитель x1.1 на {duration} сек\n⏰ Краши будут выше!"
    
    await msg.bot.send_message(msg.chat.id, text)
    
    core.logs.add_log(
        admin_id=msg.from_user.id,
        action="event_start",
        details=f"{event_name} на {duration} сек"
    )
    
    asyncio.create_task(auto_end_event(msg.bot, msg.chat.id, duration, event_name))

async def auto_end_event(bot, chat_id, duration, event_name):
    """Автоматическое завершение ивента"""
    await asyncio.sleep(duration)
    if core.events.active_event:
        core.events.end_event()
        if event_name == 'money':
            await bot.send_message(chat_id, "⏰ ИВЕНТ ЗАВЕРШЕН")
        else:
            await bot.send_message(chat_id, "⏰ КРАШ ИВЕНТ ЗАВЕРШЕН")

async def cmd_event_status(msg: Message):
    """Статус текущего ивента"""
    event = core.events.get_active_event()
    
    if not event:
        await msg.reply("🎉 Сейчас нет ивента")
        return
    
    remaining = core.events.get_remaining_seconds()
    
    if event['name'] == 'money':
        text = (
            f"🎉 ИВЕНТ АКТИВЕН\n\n"
            f"💰 x{event['multiplier']}\n"
            f"⏰ Осталось: {core.events.format_time(remaining)}"
        )
    else:
        text = (
            f"💥 КРАШ ИВЕНТ\n\n"
            f"📈 Минимальный множитель: x{event['multiplier']}\n"
            f"⏰ Осталось: {core.events.format_time(remaining)}"
        )
    
    await msg.reply(text)

async def cmd_event_end(msg: Message):
    """Завершить ивент досрочно (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    if not core.events.active_event:
        await msg.reply("❌ Нет активного ивента")
        return
    
    event_name = core.events.active_event['name']
    core.events.end_event()
    
    await msg.reply(f"✅ Ивент завершён")
    
    if event_name == 'money':
        await msg.bot.send_message(msg.chat.id, "⏰ ИВЕНТ ЗАВЕРШЁН ДОСРОЧНО")
    else:
        await msg.bot.send_message(msg.chat.id, "⏰ КРАШ ИВЕНТ ЗАВЕРШЁН ДОСРОЧНО")
    
    core.logs.add_log(
        admin_id=msg.from_user.id,
        action="event_end",
        details=f"Досрочное завершение"
    )

async def cmd_event_history(msg: Message):
    """История ивентов"""
    if not is_admin(msg.from_user.id):
        return
    
    history = core.events.get_history()
    
    if not history:
        await msg.reply("📭 История пуста")
        return
    
    text = "📊 ИСТОРИЯ ИВЕНТОВ\n\n"
    
    for i, event in enumerate(reversed(history), 1):
        start = datetime.datetime.fromisoformat(event['start_time']).strftime("%d.%m %H:%M")
        end = datetime.datetime.fromisoformat(event['end_time']).strftime("%H:%M")
        
        if event['name'] == 'money':
            text += f"{i}. MONEY x{event['multiplier']} | {start}-{end}\n"
        else:
            text += f"{i}. CRASH x{event['multiplier']} | {start}-{end}\n"
    
    await msg.reply(text)

# ========== Игровые команды ==========

async def cmd_coin(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        choice = args[1].lower().replace('ё','е')
        if choice not in ['орёл', 'орел', 'решка']:
            await msg.reply("❌ орёл или решка")
            return
        choice = 'орёл' if choice in ['орёл', 'орел'] else 'решка'
        res = core.games.coin(msg.from_user.id, bet, choice)
        event_text = res.get('event', '')
        if res['win']:
            await msg.reply(f"✅ {res['res']}\n+{fmt(res['amount'])}{event_text}\n💰 {fmt(res['balance'])}")
        else:
            await msg.reply(f"❌ {res['res']}\n-{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🦅 Орёл", callback_data=f"coin_{bet}_орёл"),
             InlineKeyboardButton(text="🪙 Решка", callback_data=f"coin_{bet}_решка")]
        ])
        await msg.reply(f"💰 {fmt(bet)}\nВыбери:", reply_markup=kb)
    else:
        await msg.reply("❌ монетка [ставка] [орёл/решка]")

async def cmd_slots(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        res = await core.games.slots(msg, msg.from_user.id, bet)
        event_text = res.get('event', '')
        if res['win']:
            await msg.reply(f"✅ x{res['mult']}\n+{fmt(res['amount'])}{event_text}\n💰 {fmt(res['balance'])}")
        else:
            await msg.reply(f"❌ -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    else:
        await msg.reply("❌ слоты [ставка]")

async def cmd_dice(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        try:
            pred = int(args[1])
        except:
            await msg.reply("❌ Число от 1 до 6")
            return
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        if pred < 1 or pred > 6:
            await msg.reply("❌ От 1 до 6")
            return
        
        res = await core.games.dice(msg, msg.from_user.id, bet, pred)
        event_text = res.get('event', '')
        if res['win']:
            await msg.reply(f"✅ {res['roll']}\n+{fmt(res['amount'])}{event_text}\n💰 {fmt(res['balance'])}")
        else:
            await msg.reply(f"❌ {res['roll']}\n-{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(1,4)],
            [InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(4,7)]
        ])
        await msg.reply(f"💰 {fmt(bet)}\nЧисло:", reply_markup=kb)
    else:
        await msg.reply("❌ кубик [ставка] [число]")

async def cmd_crash(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        try:
            target = float(args[1].replace(',','.'))
        except:
            await msg.reply("❌ Неверный множитель")
            return
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        if target < 1.1 or target > 100:
            await msg.reply("❌ От 1.1 до 100")
            return
        res = core.crash.start(msg.from_user.id, bet, target)
        event_text = res.get('event', '')
        if res['win']:
            await msg.reply(f"🚀Улетела до x{res['crash']}\n✅Ваш выигрыш +{fmt(res['amount'])}{event_text}\n -------------------------------------\n💰Новый баланс {fmt(res['balance'])}")
        else:
            await msg.reply(f"💥Ракета взорвалась x{res['crash']}\n❌Проиграно -{fmt(res['amount'])}\n -------------------------------------\n💰Новый баланс {fmt(res['balance'])}")
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1.5x", callback_data=f"crash_{bet}_1.5"),
             InlineKeyboardButton(text="2x", callback_data=f"crash_{bet}_2"),
             InlineKeyboardButton(text="3x", callback_data=f"crash_{bet}_3")],
            [InlineKeyboardButton(text="5x", callback_data=f"crash_{bet}_5"),
             InlineKeyboardButton(text="10x", callback_data=f"crash_{bet}_10"),
             InlineKeyboardButton(text="20x", callback_data=f"crash_{bet}_20")]
        ])
        await msg.reply(f"🚀 Краш\n💰 {fmt(bet)}\nМножитель:", reply_markup=kb)
    else:
        await msg.reply("❌ краш [ставка] [икс]")

async def cmd_mines(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        mines = int(args[1]) if len(args) > 1 else 1
        
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        if mines < 1 or mines > 6:
            await msg.reply("❌ Мин от 1 до 6")
            return
        
        res = core.mines.start(msg.from_user.id, bet, mines)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        await msg.reply(
            f"💣 Мины | 💣 {mines} мин\n"
            f"💰Ставка {fmt(bet)}\n"
            f"📈Множитель x1.0\n\n"
            f"Клетки:",
            reply_markup=core.mines.kb(msg.from_user.id, res['data']['field'])
        )
    else:
        await msg.reply("❌ мины [ставка] [мин]")

async def cmd_tower(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        mines = int(args[1]) if len(args) > 1 else 1
        
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        if mines < 1 or mines > 4:
            await msg.reply("❌ Мин от 1 до 4")
            return
        
        res = core.tower.start(msg.from_user.id, bet, mines)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        mults = core.tower.mults(mines)
        max_mult = mults[-1]
        
        await msg.reply(
            f"🏗️ Башня | 1/9 | 💣 {mines} мин\n"
            f"💰Ставка {fmt(bet)}\n"
            f"📈 Максимальный x{max_mult}\n\n"
            f"Клетка:",
            reply_markup=core.tower.kb(msg.from_user.id, res['data'])
        )
    else:
        await msg.reply("❌ башня [ставка] [мин]")

async def cmd_diamonds(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        mines = int(args[1]) if len(args) > 1 else 1
        
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        if mines < 1 or mines > 2:
            await msg.reply("❌ Мин от 1 до 2")
            return
        
        res = core.diamonds.start(msg.from_user.id, bet, mines)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        mults = core.diamonds.mults(mines)
        max_mult = mults[-1]
        
        await msg.reply(
            f"💎 Алмазы | 1/9 | 💣 {mines} мины\n"
            f"💰Ставка {fmt(bet)}\n"
            f"📈 Максимальный x{max_mult}\n\n",
            reply_markup=core.diamonds.kb(msg.from_user.id, res['data'])
        )
    else:
        await msg.reply("❌ алмазы [ставка] [мин]")

async def cmd_quack(msg: Message, command: CommandObject):
    """Игра Квак"""
    u = core.db.get(msg.from_user.id)
    
    if not command.args:
        await msg.reply(core.quack.get_info())
        return
    
    bet = core.parse_bet(command.args, u['balance'])
    
    if bet <= 0 or bet > u['balance']:
        await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
        return
    
    res = core.quack.start(msg.from_user.id, bet)
    if not res['ok']:
        await msg.reply(res['msg'])
        return
    
    g = res['data']
    
    await msg.reply(
        f"🐸 КВАК | 1/4 | 💣 {core.quack.mines_count[0]} мины\n"
        f"💰 {fmt(bet)}\n"
        f"📈 x1.21\n\n"
        f"Клетка (ряд снизу):",
        reply_markup=core.quack.kb(msg.from_user.id, g)
    )

async def cmd_pyramid(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        doors = int(args[1]) if len(args) > 1 else 3
        
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        if doors < 1 or doors > 3:
            await msg.reply("❌ Дверей от 1 до 3")
            return
        
        res = core.pyramid.start(msg.from_user.id, bet, doors)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        mults = core.pyramid.multipliers[doors]
        max_mult = mults[-1]
        
        field = core.pyramid.format_field(res['data']['levels'])
        
        await msg.reply(
            f"🔺 Пирамида | 1/12 | 🚪 {doors} двери\n"
            f"💰 {fmt(bet)}\n"
            f"📈 Макс x{max_mult:.2f}\n\n"
            f"{field}\n"
            f"Дверь:",
            reply_markup=core.pyramid.kb(msg.from_user.id, res['data'])
        )
    else:
        await msg.reply(
            "🔺 Пирамида\n\n"
            "пирамида [ставка] [дверей]\n"
            "пример: пирамида 1000 (3 двери по умолчанию)\n\n"
            "Множители:\n"
            "1 дверь: x1.7 → x2.3 → x3.1 → x4.2 → x5.7 → x7.7 → x10.4 → x14.0 → x18.9 → x25.5 → x34.4 → x46.4\n"
            "2 двери: x1.5 → x2.0 → x2.7 → x3.6 → x4.9 → x6.6 → x8.9 → x12.0 → x16.2 → x21.9 → x29.6 → x40.0\n"
            "3 двери: x1.31 → x1.74 → x2.32 → x3.10 → x4.13 → x5.51 → x7.34 → x9.79 → x13.05 → x17.40 → x23.20 → x30.93"
        )

async def cmd_roulette(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 2:
        bet = core.parse_bet(args[0], u['balance'])
        btype = args[1].lower()
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        type_map = {'чет':'even','нечет':'odd','even':'even','odd':'odd','красное':'red','red':'red','чёрное':'black','black':'black',
                   '1-12':'1-12','13-24':'13-24','25-36':'25-36','зеро':'zero','zero':'zero'}
        val = None
        if btype in type_map:
            btype = type_map[btype]
        else:
            try:
                val = int(btype)
                if 0 <= val <= 36:
                    btype = 'number'
                else:
                    await msg.reply("❌ Неверный тип")
                    return
            except:
                await msg.reply("❌ Неверный тип")
                return
        res = core.roulette.play(msg.from_user.id, bet, btype, val)
        event_text = res.get('event', '')
        if res['win']:
            await msg.reply(f"🎰 {res['color']} {res['num']}\n✅ x{res['mult']}\n+{fmt(res['amount'])}{event_text}\n💰 {fmt(res['balance'])}")
        else:
            await msg.reply(f"🎰 {res['color']} {res['num']}\n❌ -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    else:
        await msg.reply("❌ рулетка [ставка] [чет/нечет/красное/чёрное/1-12/13-24/25-36/зеро/число]")

async def cmd_gold(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        chat_id = msg.chat.id
        
        res = core.gold.start(msg.from_user.id, bet, chat_id)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        await msg.reply(
            f"{core.gold.display(res['data'])}\n\n💰 {fmt(bet)}\n🎯 0/12\nСторона:",
            reply_markup=core.gold.kb(msg.from_user.id, res['data'])
        )
    else:
        await msg.reply("❌ золото [ставка]")

async def cmd_risk(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        chat_id = msg.chat.id
        
        res = core.risk.start(msg.from_user.id, bet, chat_id)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        await msg.reply(
            f"{core.risk.display(res['data'])}\n\nКлетка:",
            reply_markup=core.risk.kb(msg.from_user.id, res['data'])
        )
    else:
        await msg.reply("❌ риск [ставка]")

async def cmd_football(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        choice = args[1].lower()
        if choice not in ['гол', 'мимо']:
            await msg.reply("❌ гол или мимо")
            return
        
        res = await core.ball_games.play_football(msg, msg.from_user.id, bet, choice)
        
        if res['win']:
            await msg.reply(
                f"⚽ Футбол\n"
                f"Результат {res['emoji']} {res['result_text']}\n"
                f"✅ Ты выиграл! +{fmt(res['amount'])}{res.get('event', '')}\n"
                f"-------------------------------------\n"
                f"💰Новый баланс {fmt(res['balance'])}"
            )
        else:
            await msg.reply(
                f"⚽ Футбол\n"
                f"{res['emoji']} {res['result_text']}\n"
                f"❌ Ты проиграл! -{fmt(res['amount'])}\n"
                f"-------------------------------------\n"
                f"💰Новый баланс {fmt(res['balance'])}"
            )
    
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚽ ГОЛ", callback_data=f"football_{bet}_гол"),
             InlineKeyboardButton(text="🥅 МИМО", callback_data=f"football_{bet}_мимо")]
        ])
        await msg.reply(f"⚽ Футбол\n💰 {fmt(bet)}\nВыбери:", reply_markup=kb)
    else:
        await msg.reply("⚽ футбол [ставка] [гол/мимо]\nПример: футбол 1000 гол")

async def cmd_basketball(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        choice = args[1].lower()
        if choice not in ['гол', 'мимо']:
            await msg.reply("❌ гол или мимо")
            return
        
        res = await core.ball_games.play_basketball(msg, msg.from_user.id, bet, choice)
        
        if res['win']:
            await msg.reply(
                f"🏀 Баскетбол\n"
                f"{res['emoji']} {res['result_text']}\n"
                f"✅ Ты выиграл! +{fmt(res['amount'])}{res.get('event', '')}\n"
                f"💰 {fmt(res['balance'])}"
            )
        else:
            await msg.reply(
                f"🏀 Баскетбол\n"
                f"{res['emoji']} {res['result_text']}\n"
                f"❌ Ты проиграл! -{fmt(res['amount'])}\n"
                f"💰 {fmt(res['balance'])}"
            )
    
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏀 ГОЛ", callback_data=f"basketball_{bet}_гол"),
             InlineKeyboardButton(text="🧺 МИМО", callback_data=f"basketball_{bet}_мимо")]
        ])
        await msg.reply(f"🏀 Баскетбол\n💰 {fmt(bet)}\nВыбери:", reply_markup=kb)
    else:
        await msg.reply("🏀 баскетбол [ставка] [гол/мимо]\nПример: баскетбол 1000 гол")

async def cmd_dart(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        choice = args[1].lower()
        valid_choices = ['центр', 'красное', 'белое', 'мимо']
        if choice not in valid_choices:
            await msg.reply("❌ Выбери: центр, красное, белое, мимо")
            return
        
        res = await core.dart.play(msg, msg.from_user.id, bet, choice)
        
        sector = res['sector']
        
        if res['win']:
            multiplier = f"x{sector['mult']}"
            await msg.reply(
                f"🎯 ДАРТС\n\n"
                f"{sector['emoji']} {sector['name']}! [{res['value']}] {multiplier}\n"
                f"✅ Ты угадал! +{fmt(res['amount'])}{res.get('event', '')}\n"
                f"💰 Баланс: {fmt(res['balance'])}"
            )
        else:
            result_text = f"{sector['emoji']} {sector['name']}! [{res['value']}]"
            if choice == 'мимо':
                result_text += f" (x{sector['mult']} если бы угадал)"
            
            await msg.reply(
                f"🎯 ДАРТС\n\n"
                f"{result_text}\n"
                f"❌ Ты не угадал! -{fmt(res['amount'])}\n"
                f"💰 Баланс: {fmt(res['balance'])}"
            )
    
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']:
            await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
            return
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 ЦЕНТР (x3)", callback_data=f"dart_{bet}_центр"),
             InlineKeyboardButton(text="🔴 КРАСНОЕ (x2)", callback_data=f"dart_{bet}_красное")],
            [InlineKeyboardButton(text="⚪ БЕЛОЕ (x1.5)", callback_data=f"dart_{bet}_белое"),
             InlineKeyboardButton(text="💢 МИМО (x1)", callback_data=f"dart_{bet}_мимо")]
        ])
        
        await msg.reply(
            f"🎯 ДАРТС\n\n"
            f"💰 Ставка: {fmt(bet)}\n"
            f"🎲 Множители при попадании:\n"
            f"• Центр 🎯 - x3\n"
            f"• Красное 🔴 - x2\n"
            f"• Белое ⚪ - x1.5\n"
            f"• Мимо 💢 - x1 (возврат ставки)\n\n"
            f"Куда целишься?",
            reply_markup=kb
        )
    else:
        await msg.reply(
            "🎯 ДАРТС\n\n"
            "дартс [ставка] [центр/красное/белое/мимо]\n"
            "пример: дартс 1000 центр\n\n"
            "Множители при попадании:\n"
            "• Центр 🎯 - x3\n"
            "• Красное 🔴 - x2\n"
            "• Белое ⚪ - x1.5\n"
            "• Мимо 💢 - x1 (возврат ставки)"
        )

async def cmd_knb(msg: Message, command: CommandObject, state: FSMContext):
    u = core.db.get(msg.from_user.id)
    
    if not command.args:
        await msg.reply(
            "🪨 КНБ\n\n"
            "кнб [ставка]\n"
            "пример: кнб 1000\n\n"
            "💰 x2"
        )
        return
    
    bet = core.parse_bet(command.args, u['balance'])
    
    if bet <= 0 or bet > u['balance']:
        await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
        return
    
    core.db.update(msg.from_user.id, balance=u['balance'] - bet)
    
    bot_choice = core.knb.bot_choice()
    
    await state.update_data(
        knb_bet=bet,
        knb_bot_choice=bot_choice,
        knb_player_id=msg.from_user.id
    )
    await state.set_state(KNBTicTacToe.waiting_choice)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 Камень", callback_data="knb_choice_камень"),
            InlineKeyboardButton(text="✂️ Ножницы", callback_data="knb_choice_ножницы"),
            InlineKeyboardButton(text="📄 Бумага", callback_data="knb_choice_бумага")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="knb_cancel")]
    ])
    
    await msg.reply(
        f"🪨 КНБ\n"
        f"💰 {fmt(bet)}\n\n"
        f"Твой выбор:",
        reply_markup=kb
    )

async def cmd_knb_duel(msg: Message, command: CommandObject, state: FSMContext):
    u = core.db.get(msg.from_user.id)
    
    if not command.args:
        await msg.reply(
            "⚔️ Дуэль КНБ\n\n"
            "дуэль кнб [ставка]\n"
            "пример: дуэль кнб 1000"
        )
        return
    
    bet = core.parse_bet(command.args, u['balance'])
    
    if bet <= 0 or bet > u['balance']:
        await msg.reply(f"❌ Неверная ставка, баланс {fmt(u['balance'])}")
        return
    
    core.db.update(msg.from_user.id, balance=u['balance'] - bet)
    
    duel_id = core.knb.create_duel(msg.from_user.id, bet, msg.chat.id, msg.message_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Принять", callback_data=f"knb_join_{duel_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"knb_cancel_duel_{duel_id}")]
    ])
    
    await msg.reply(
        f"⚔️ Дуэль создана\n"
        f"👤 {msg.from_user.first_name}\n"
        f"💰 {fmt(bet)}\n"
        f"🎫 ID {duel_id}\n\n"
        f"Ожидание...",
        reply_markup=kb
    )

async def cmd_give(msg: Message):
    """Перевод денег другому пользователю с возможностью указать причину"""
    if not msg.reply_to_message:
        await msg.reply("❌ Ответь на сообщение")
        return
    
    to_id = msg.reply_to_message.from_user.id
    from_id = msg.from_user.id
    
    if from_id == to_id:
        await msg.reply("❌ Себе нельзя")
        return
    
    # Разбираем сообщение: "дать [сумма] [причина]" или "дай [сумма] [причина]"
    parts = msg.text.split(maxsplit=2)
    
    if len(parts) < 2 or parts[0].lower() not in ['дать', 'дай']:
        await msg.reply("❌ дать [сумма] [комментарий] (комментарий необязателен)")
        return
    
    amount_str = parts[1]
    reason = parts[2] if len(parts) > 2 else ""
    
    sender = core.db.get(from_id)
    
    if amount_str in ['всё', 'все']:
        amount = sender['balance']
    else:
        amount = core.parse_bet(amount_str, sender['balance'])
    
    if amount <= 0:
        await msg.reply("❌ Неверная сумма")
        return
    
    if sender['balance'] < amount:
        await msg.reply(f"❌ Не хватает, баланс {fmt(sender['balance'])}")
        return
    
    commission = int(amount * 0.1)  # 10% комиссия
    receive_amount = amount - commission
    
    # Обновляем балансы
    core.db.update(from_id, balance=sender['balance'] - amount)
    
    receiver = core.db.get(to_id)
    core.db.update(to_id, balance=receiver['balance'] + receive_amount)
    
    # Формируем сообщение
    reason_text = f"\n💬 Комментарий: {reason}" if reason else ""
    
    await msg.reply(
        f"✅ {msg.reply_to_message.from_user.full_name} получил {fmt(receive_amount)}\n"
        f"💰 Комиссия {fmt(commission)}{reason_text}"
    )
    
    # Отправляем уведомление получателю
    try:
        await msg.bot.send_message(
            to_id,
            f"💰 Тебе перевели {fmt(receive_amount)}\n"
            f"👤 От: {msg.from_user.full_name}"
            f"💬 Комментарий: {reason_text}"
        )
    except:
        pass

# ========== Команда логов ==========

async def cmd_logs(msg: Message):
    """Просмотр логов админов (только для админов)"""
    if not is_admin(msg.from_user.id):
        await msg.reply("❌ Только для админов")
        return
    
    parts = msg.text.split(maxsplit=1)
    admin_id = None
    
    if len(parts) > 1:
        try:
            admin_id = int(parts[1])
            if not core.admins.get_admin_info(admin_id):
                await msg.reply(f"❌ Админ с ID {admin_id} не найден")
                return
        except ValueError:
            await msg.reply("❌ Неверный ID админа")
            return
    
    logs = core.logs.get_logs(limit=50, admin_id=admin_id)
    
    if admin_id:
        try:
            admin_chat = await msg.bot.get_chat(admin_id)
            title = f"📋 Логи {admin_chat.first_name}"
        except:
            title = f"📋 Логи ID: {admin_id}"
    else:
        title = "📋 Все логи админов"
    
    if not logs:
        await msg.reply(f"{title}\n\n📭 Логов нет")
        return
    
    text = core.logs.format_logs(logs, detailed=True)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="logs_stats"),
            InlineKeyboardButton(text="🧹 Очистить логи", callback_data="logs_clear")
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="logs_refresh")]
    ])
    
    if admin_id:
        kb.inline_keyboard.append([InlineKeyboardButton(text="◀️ Все логи", callback_data="logs_all")])
    
    await msg.reply(f"{title}\n\n{text}", reply_markup=kb)

# ========== Команда топ общий ==========

async def cmd_top_total(msg: Message):
    """Показывает общий топ (наличные + карта)"""
    if not is_admin(msg.from_user.id):
        await msg.reply("❌ Только для админов")
        return
    
    parts = msg.text.split(maxsplit=2)
    
    # Если указан ID пользователя
    if len(parts) > 2:
        try:
            target_id = int(parts[2])
            
            # Проверяем, существует ли пользователь
            try:
                user_data = core.db.get(target_id)
                user_chat = await msg.bot.get_chat(target_id)
                user_name = user_chat.full_name
            except:
                await msg.reply(f"❌ Пользователь с ID {target_id} не найден")
                return
            
            total = core.db.get_total_balance(target_id)
            bank_data = core.bank.get(target_id)
            
            text = (
                f"👤 ОБЩИЙ БАЛАНС\n\n"
                f"👤 {user_name}\n"
                f"🆔 <code>{target_id}</code>\n\n"
                f"💰 Наличные: {fmt(user_data['balance'])}\n"
                f"💳 На карте: {fmt(bank_data['card_balance'])}\n"
                f"💎 ВСЕГО: {fmt(total)}"
            )
            
            await msg.reply(text, parse_mode="HTML")
            return
            
        except ValueError:
            await msg.reply("❌ Неверный ID")
            return
    
    # Показываем топ
    users = core.db.get_all_users_total_balance()
    
    if not users:
        await msg.reply("📊 Пока нет пользователей")
        return
    
    text = "🏆 ОБЩИЙ ТОП (наличные + карта)\n\n"
    
    for i, (uid, total, cash, card) in enumerate(users[:15], 1):
        try:
            chat = await msg.bot.get_chat(int(uid))
            name = chat.first_name
        except:
            name = f"ID {uid[-4:]}"
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name} — {fmt(total)}\n"
        text += f"   💰 {fmt(cash)} + 💳 {fmt(card)}\n"
    
    await msg.reply(text)

# ========== Команда выдать статус ==========

async def cmd_give_status(msg: Message):
    """Выдаёт статус по названию (только создатель)"""
    if not is_creator(msg.from_user.id):
        await msg.reply("❌ Только создатель")
        return
    
    if not msg.reply_to_message:
        await msg.reply("❌ Ответь на сообщение пользователя")
        return
    
    # Правильный парсинг сообщения
    text = msg.text
    
    # Убираем "выдать статус " из начала
    if text.startswith('выдать статус '):
        status_name = text[14:].strip()  # 14 = длина "выдать статус "
    else:
        # Если написали по-другому, пробуем другие варианты
        parts = text.split(maxsplit=2)
        if len(parts) >= 3:
            status_name = parts[2].strip()
        else:
            await msg.reply("❌ выдать статус [название]\nПример: выдать статус Легенда")
            return
    
    target_id = msg.reply_to_message.from_user.id
    
    # Ищем статус по названию
    status_id, status = core.status.get_status_by_name(status_name)
    
    if not status:
        # Пробуем найти по части названия
        statuses = core.status.all()
        found = []
        for sid, s in statuses.items():
            if status_name.lower() in s['name'].lower():
                found.append(s['name'])
        
        if found:
            await msg.reply(f"❌ Статус '{status_name}' не найден\n\nВозможно, вы имели в виду:\n{', '.join(found)}")
        else:
            await msg.reply(f"❌ Статус '{status_name}' не найден")
        return
    
    # Проверяем, не создатель ли это
    if is_creator(target_id):
        await msg.reply("❌ Нельзя выдать статус создателю")
        return
    
    # Выдаём статус
    res = core.status.admin_give_status(target_id, status_id, core.db)
    
    if res['ok']:
        # Логируем действие
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="give_status",
            target_id=target_id,
            details=f"Статус: {status['name']} (был: {core.db.get(target_id)['status']})"
        )
        
        # Отправляем уведомление
        await msg.reply(res['msg'])
        
        # Уведомляем пользователя
        try:
            await msg.bot.send_message(
                target_id,
                f"👑 Тебе выдан статус {status['emoji']} {status['name']}!"
            )
        except:
            pass
    else:
        await msg.reply(res['msg'])

async def cmd_status_list(msg: Message):
    """Показывает список всех статусов (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    statuses = core.status.all()
    
    text = "📋 ДОСТУПНЫЕ СТАТУСЫ\n\n"
    for status_id, status in statuses.items():
        if status.get('sell', True):
            price_info = f" | 💰 {fmt(status['price'])}"
        else:
            price_info = " | 🚫 не продаётся"
        
        text += f"{status['emoji']} {status['name']}{price_info}\n"
        text += f"   🆔 {status_id}\n"
        text += f"   📝 {status['description']}\n"
        text += f"   💰 бонус: {fmt(status['min_bonus'])} - {fmt(status['max_bonus'])}\n\n"
    
    await msg.reply(text)

async def cmd_cancel_transfer(msg: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await msg.reply("❌ Отменено")
    else:
        await msg.reply("❌ Нет активного действия")

async def cmd_help(msg):
    help_text = """
Игры:
• монетка [ставка] [орёл/решка]
• кубик [ставка] [1-6]
• слоты [ставка]
• мины [ставка] [мин]
• башня [ставка] [мин]
• алмазы [ставка] [мин]
• пирамида [ставка] [дверей] (по умолчанию 3)
• краш [ставка] [икс]
• футбол [ставка] [гол/мимо]
• баскетбол/бс [ставка] [гол/мимо]
• дартс [ставка] [центр/красное/белое/мимо]
• квак [ставка] - 4 ряда с возрастающими минами
• кнб [ставка]
• дуэль кнб [ставка]

Банк:
• банк
• карта
• положить [сумма]
• снять [сумма]
• вклад [сумма] [дни]
• кредит [сумма] [дни]

Переводы:
• дать [сумма] [причина] - перевести деньги с комиссией 10% (причина необязательна)

Задания:
• заработать - список доступных заданий
• реклама - создать своё задание
• мои_задания - посмотреть свои задания
• проверка_канала [username] - проверить статус бота в канале (админ)

NFT (только в личке):
• мои нфт / инвентарь
• магазин / нфт
• рынок

Прочее:
• профиль / п
• статус
• бонус (раз в час)
• топ
• промо [код]

Форматы:
• 1к = 1000
• 1кк = 1 000 000
• всё
"""
    await msg.reply(help_text)

async def handle_market_price(msg: Message, state: FSMContext):
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.reply("❌ Отменено")
        return
    
    data = await state.get_data()
    nft_id = data.get('sell_nft_id')
    if not nft_id:
        await state.clear()
        return
    
    uid = str(msg.from_user.id)
    inventory = core.shop.inventory(uid)
    nft = next((item for item in inventory if item['unique_id'] == nft_id), None)
    
    if not nft:
        await msg.reply("❌ NFT не найден")
        await state.clear()
        return
    
    price = core.parse_bet(msg.text)
    if price <= 0:
        await msg.reply("❌ Цена > 0")
        return
    
    res = core.market.add_listing(msg.from_user.id, nft, price)
    await msg.reply(res['msg'])
    
    if res['ok']:
        await show_nft_list(msg, uid, 0)
    
    await state.clear()

async def callback_handler(cb: CallbackQuery, state: FSMContext):
    data = cb.data
    uid = cb.from_user.id
    chat_id = cb.message.chat.id
    
    try:
        if data == "ignore":
            await cb.answer()
            return
        
        if data == "back_to_main":
            await cmd_start(cb)
            await cb.answer()
            return
        
        if data == "menu_games":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲 На удачу", callback_data="games_luck")],
                [InlineKeyboardButton(text="🧠 Стратегии", callback_data="games_strategy")],
                [InlineKeyboardButton(text="⚔️ Дуэли", callback_data="games_duel")],
                [InlineKeyboardButton(text="⚽ Спорт", callback_data="games_sport")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ])
            await cb.message.edit_text(
                "Категории:\n\n"
                "🎲 На удачу - монетка, кубик, слоты\n"
                "🧠 Стратегии - мины, башня, пирамида, квак\n"
                "⚔️ Дуэли - кнб, дуэль\n"
                "⚽ Спорт - футбол, баскетбол, дартс",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data == "games_luck":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🪙 Монетка", callback_data="game_coin"),
                 InlineKeyboardButton(text="🎲 Кубик", callback_data="game_dice")],
                [InlineKeyboardButton(text="🎰 Слоты", callback_data="game_slots"),
                 InlineKeyboardButton(text="💰 Золото", callback_data="game_gold")],
                [InlineKeyboardButton(text="🎰 Рулетка", callback_data="game_roulette")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
            ])
            await cb.message.edit_text(
                "На удачу:\n\n"
                "🪙 Монетка - орёл/решка (x2)\n"
                "🎲 Кубик - число 1-6 (x6)\n"
                "🎰 Слоты - до x10\n"
                "💰 Золото - 50/50\n"
                "🎰 Рулетка - классика",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data == "games_strategy":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💣 Мины", callback_data="game_mines"),
                 InlineKeyboardButton(text="🏗️ Башня", callback_data="game_tower")],
                [InlineKeyboardButton(text="💎 Алмазы", callback_data="game_diamonds"),
                 InlineKeyboardButton(text="🔺 Пирамида", callback_data="game_pyramid")],
                [InlineKeyboardButton(text="🚀 Краш", callback_data="game_crash"),
                 InlineKeyboardButton(text="🐸 Квак", callback_data="game_quack")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
            ])
            await cb.message.edit_text(
                "Стратегии:\n\n"
                "💣 Мины - не наступи на мину\n"
                "🏗️ Башня - лезь наверх\n"
                "💎 Алмазы - ищи алмазы\n"
                "🔺 Пирамида - 2x2 поле\n"
                "🚀 Краш - забери до взрыва\n"
                "🐸 Квак - 4 ряда с возрастающими минами",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data == "games_duel":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🪨 КНБ с ботом", callback_data="game_knb")],
                [InlineKeyboardButton(text="⚔️ Дуэль с игроком", callback_data="game_knb_duel")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
            ])
            await cb.message.edit_text(
                "Дуэли:\n\n"
                "🪨 КНБ с ботом\n"
                "⚔️ Дуэль с игроком",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data == "games_sport":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football"),
                 InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basketball")],
                [InlineKeyboardButton(text="🎯 Дартс", callback_data="game_dart"),
                 InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
            ])
            await cb.message.edit_text(
                "Спорт:\n\n"
                "⚽ Футбол - забей гол\n"
                "🏀 Баскетбол - забрось мяч\n"
                "🎯 Дартс - брось дротик",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data == "back_to_games":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲 На удачу", callback_data="games_luck")],
                [InlineKeyboardButton(text="🧠 Стратегии", callback_data="games_strategy")],
                [InlineKeyboardButton(text="⚔️ Дуэли", callback_data="games_duel")],
                [InlineKeyboardButton(text="⚽ Спорт", callback_data="games_sport")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ])
            await cb.message.edit_text(
                "Категории:\n\n"
                "🎲 На удачу - монетка, кубик, слоты\n"
                "🧠 Стратегии - мины, башня, пирамида, квак\n"
                "⚔️ Дуэли - кнб, дуэль\n"
                "⚽ Спорт - футбол, баскетбол, дартс",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data == "menu_earn":
            await cmd_earn(cb.message)
            await cb.answer()
            return
        
        if data == "menu_nft":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖼 Мои NFT", callback_data="nft_my"),
                 InlineKeyboardButton(text="🏪 Магазин", callback_data="nft_shop")],
                [InlineKeyboardButton(text="🏪 Рынок", callback_data="nft_market"),
                 InlineKeyboardButton(text="🔄 Передать", callback_data="nft_transfer")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ])
            await cb.message.edit_text("NFT:", reply_markup=kb)
            await cb.answer()
            return
        
        if data == "nft_my":
            await cmd_my_nft(cb.message)
            await cb.answer()
            return
        
        if data == "nft_shop":
            await cmd_nft_shop(cb.message)
            await cb.answer()
            return
        
        if data == "nft_market":
            await cmd_market(cb.message)
            await cb.answer()
            return
        
        if data == "nft_transfer":
            await cmd_transfer_nft_start(cb.message, state)
            await cb.answer()
            return
        
        if data.startswith("game_"):
            game = data[5:]
            user = core.db.get(uid)
            
            game_names = {
                "coin": "🪙 Монетка",
                "dice": "🎲 Кубик",
                "slots": "🎰 Слоты",
                "mines": "💣 Мины",
                "tower": "🏗️ Башня",
                "diamonds": "💎 Алмазы",
                "pyramid": "🔺 Пирамида",
                "crash": "🚀 Краш",
                "football": "⚽ Футбол",
                "basketball": "🏀 Баскетбол",
                "dart": "🎯 Дартс",
                "gold": "💰 Золото",
                "roulette": "🎰 Рулетка",
                "knb": "🪨 КНБ",
                "knb_duel": "⚔️ Дуэль",
                "quack": "🐸 Квак"
            }
            
            title = game_names.get(game, game)
            
            if game == "quack":
                # Для Квак показываем информацию
                await cb.message.edit_text(core.quack.get_info())
                await cb.answer()
                return
            
            # Для остальных игр показываем выбор ставки
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="100", callback_data=f"{game}_100"),
                 InlineKeyboardButton(text="500", callback_data=f"{game}_500"),
                 InlineKeyboardButton(text="1к", callback_data=f"{game}_1000")],
                [InlineKeyboardButton(text="5к", callback_data=f"{game}_5000"),
                 InlineKeyboardButton(text="10к", callback_data=f"{game}_10000"),
                 InlineKeyboardButton(text="50к", callback_data=f"{game}_50000")],
                [InlineKeyboardButton(text="💰 Всё", callback_data=f"{game}_all"),
                 InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
            ])
            
            await cb.message.edit_text(
                f"{title}\n"
                f"💰 {fmt(user['balance'])}\n\n"
                f"Ставка:",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data.startswith('coin_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, choice = int(parts[1]), parts[2]
                
                user = core.db.get(uid)
                if user['balance'] < bet:
                    await cb.answer("❌ Не хватает", show_alert=True)
                    return
                
                res = core.games.coin(uid, bet, choice)
                event_text = res.get('event', '')
                if res['win']:
                    await cb.message.edit_text(f"✅ {res['res']}\n+{fmt(res['amount'])}{event_text}\n💰 {fmt(res['balance'])}")
                else:
                    await cb.message.edit_text(f"❌ {res['res']}\n-{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
            await cb.answer()
            return
        
        if data.startswith('dice_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, num = int(parts[1]), int(parts[2])
                
                user = core.db.get(uid)
                if user['balance'] < bet:
                    await cb.answer("❌ Не хватает", show_alert=True)
                    return
                
                temp_msg = await cb.message.answer("🎲 ...")
                res = await core.games.dice(temp_msg, uid, bet, num)
                event_text = res.get('event', '')
                if res['win']:
                    await cb.message.edit_text(f"✅ {res['roll']}\n+{fmt(res['amount'])}{event_text}\n💰 {fmt(res['balance'])}")
                else:
                    await cb.message.edit_text(f"❌ {res['roll']}\n-{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
                await temp_msg.delete()
            await cb.answer()
            return
        
        if data.startswith('crash_'):
            if data.startswith('crash_') and data != "crash_cash_":
                parts = data.split('_')
                if len(parts) == 2:
                    bet_str = parts[1]
                    
                    user = core.db.get(uid)
                    
                    if bet_str == "all":
                        bet = user['balance']
                    else:
                        try:
                            bet = int(bet_str)
                        except:
                            await cb.answer("❌ Ошибка", show_alert=True)
                            return
                    
                    if bet <= 0 or bet > user['balance']:
                        await cb.answer(f"❌ Неверная ставка", show_alert=True)
                        return
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="1.5x", callback_data=f"crash_{bet}_1.5"),
                         InlineKeyboardButton(text="2x", callback_data=f"crash_{bet}_2"),
                         InlineKeyboardButton(text="3x", callback_data=f"crash_{bet}_3")],
                        [InlineKeyboardButton(text="5x", callback_data=f"crash_{bet}_5"),
                         InlineKeyboardButton(text="10x", callback_data=f"crash_{bet}_10"),
                         InlineKeyboardButton(text="20x", callback_data=f"crash_{bet}_20")]
                    ])
                    
                    await cb.message.edit_text(
                        f"🚀 Краш\n"
                        f"💰 {fmt(bet)}\n\n"
                        f"Множитель:",
                        reply_markup=kb
                    )
            await cb.answer()
            return
        
        if data.startswith('crash_') and len(data.split('_')) == 3:
            parts = data.split('_')
            bet, target = int(parts[1]), float(parts[2])
            
            user = core.db.get(uid)
            if user['balance'] < bet:
                await cb.answer("❌ Не хватает", show_alert=True)
                return
            
            res = core.crash.start(uid, bet, target)
            event_text = res.get('event', '')
            if res['ok']:
                if res['win']:
                    await cb.message.edit_text(f"🚀 x{res['crash']}\n✅ +{fmt(res['amount'])}{event_text}\n💰 {fmt(res['balance'])}")
                else:
                    await cb.message.edit_text(f"💥 x{res['crash']}\n❌ -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
            await cb.answer()
            return
        
        if data.startswith('mines_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, r, c = int(parts[1]), int(parts[2]), int(parts[3])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                
                res = core.mines.open(user_id, r, c)
                
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                
                if res.get('over'):
                    if res.get('win'):
                        await cb.message.edit_text(
                            f"🏆 Победа!\n"
                            f"+{fmt(res['won'])}{res.get('event', '')}\n"
                            f"📈 x{res['mult']:.2f}\n"
                            f"🎯 {res['opened']} клеток\n"
                            f"💰 {fmt(res['balance'])}",
                            reply_markup=core.mines.kb(user_id, res['field'], False)
                        )
                    else:
                        await cb.message.edit_text(
                            f"💥 Бум!\n"
                            f"❌ -{fmt(res['bet'])}\n"
                            f"🎯 {res['opened']} клеток",
                            reply_markup=core.mines.kb(user_id, res['field'], False)
                        )
                else:
                    await cb.message.edit_text(
                        f"💣 Мины | 💣 {core.mines.games[user_id]['count']} мин\n"
                        f"💰 {fmt(core.mines.games[user_id]['bet'])}\n"
                        f"🎯 {res['opened']}/{res['max']} | 📈 x{res['mult']:.2f}\n"
                        f"💎 {fmt(res['won'])}\n\n"
                        f"Клетка:",
                        reply_markup=core.mines.kb(user_id, res['field'])
                    )
            await cb.answer()
            return
        
        if data.startswith('cashout_'):
            user_id = int(data.split('_')[1])
            if uid != user_id:
                await cb.answer("❌ Не твоя игра", show_alert=True)
                return
            res = core.mines.cashout(user_id)
            if not res['ok']:
                await cb.answer(res['msg'], show_alert=True)
                return
            await cb.message.edit_text(
                f"🏆 +{fmt(res['won'])}{res.get('event', '')}\n"
                f"🎯 {res['opened']} | 📈 x{res['mult']:.2f}\n"
                f"💰 {fmt(res['balance'])}",
                reply_markup=core.mines.kb(user_id, res['field'], False)
            )
            await cb.answer()
            return
        
        if data.startswith('tower_'):
            if data.startswith('tower_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                res = core.tower.cashout(user_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(
                    f"🏆Победа +{fmt(res['won'])}{res.get('event', '')}\n"
                    f"📈Множитель x{res['mult']:.1f}\n"
                    f"🎯Пройдено {res['rows']}/9 этажей\n"
                    f"-------------------------------------\n"
                    f"💰Новый баланс {fmt(res['balance'])}"
                )
                await cb.answer()
                return
            else:
                parts = data.split('_')
                if len(parts) == 4:
                    user_id, r, c = int(parts[1]), int(parts[2]), int(parts[3])
                    if uid != user_id:
                        await cb.answer("❌ Не твоя игра", show_alert=True)
                        return
                    res = core.tower.open(user_id, r, c)
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    if res.get('over'):
                        if res.get('mine'):
                            kb = [[InlineKeyboardButton(text=res['row_data']['cells'][c], callback_data="ignore") for c in range(5)]]
                            await cb.message.edit_text(f"💥 Бум!\n❌ -{fmt(res['bet'])}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
                        else:
                            await cb.message.edit_text(
                                f"🏆 Максимум!\n"
                                f"Выигрыщ +{fmt(res['won'])}{res.get('event', '')}\n"
                                f"📈Множитель x{res['mult']:.1f}\n"
                                f"🎯Пройдено {res['rows']}/9 этажей\n"
                                f"-------------------------------------\n"
                                f"💰Новый баланс {fmt(res['balance'])}"
                            )
                    else:
                        game = core.tower.games.get(user_id)
                        if game:
                            await cb.message.edit_text(
                                f"🏗️ Башня | {game['row']+1}/9 | 💣 {game['mines']}\n"
                                f"💰Ставка {fmt(game['bet'])}\n"
                                f"📈Множитель x{res['mult']:.1f} | 💰Текущий выигрыш {fmt(res['won'])}\n\n"
                                f"Клетка:",
                                reply_markup=core.tower.kb(user_id, game)
                            )
            await cb.answer()
            return
        
        if data.startswith('diamonds_'):
            if data.startswith('diamonds_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                res = core.diamonds.cashout(user_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(
                    f"🏆Победа +{fmt(res['won'])}{res.get('event', '')}\n"
                    f"📈Множитель x{res['mult']:.1f}\n"
                    f"🎯Пройдено {res['rows']}/9 этажей\n"
                    f"-------------------------------------\n"
                    f"💰Новый баланс {fmt(res['balance'])}"
                )
                await cb.answer()
                return
            else:
                parts = data.split('_')
                if len(parts) == 4:
                    user_id, r, c = int(parts[1]), int(parts[2]), int(parts[3])
                    if uid != user_id:
                        await cb.answer("❌ Не твоя игра", show_alert=True)
                        return
                    res = core.diamonds.open(user_id, r, c)
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    if res.get('over'):
                        if res.get('mine'):
                            kb = [[InlineKeyboardButton(text=res['row_data']['cells'][c], callback_data="ignore") for c in range(3)]]
                            await cb.message.edit_text(f"💥 Бум!\n❌ -{fmt(res['bet'])}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
                        else:
                            await cb.message.edit_text(
                                f"🏆 Максимум!\n"
                                f"+{fmt(res['won'])}{res.get('event', '')}\n"
                                f"📈Множитель x{res['mult']:.1f}\n"
                                f"🎯Пройдено {res['rows']}/9 этажей\n"
                                f"-------------------------------------\n"
                                f"💰Новый баланс {fmt(res['balance'])}"
                            )
                    else:
                        game = core.diamonds.games.get(user_id)
                        if game:
                            await cb.message.edit_text(
                                f"💎 Алмазы | Этап {game['row']+1}/9 | 💣Мин {game['mines']}\n"
                                f"💰Ставка {fmt(game['bet'])}\n"
                                f"📈Множитель x{res['mult']:.1f} | Текущий выигрыш 💎 {fmt(res['won'])}\n\n",
                                reply_markup=core.diamonds.kb(user_id, game)
                            )
            await cb.answer()
            return
        
        if data.startswith('quack_'):
            if data.startswith('quack_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                res = core.quack.cashout(user_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                
                row_text = {1: "первый", 2: "второй", 3: "третий", 4: "четвёртый"}
                row_name = row_text.get(res['row'], str(res['row']))
                
                await cb.message.edit_text(
                    f"🐸 КВАК\n\n"
                    f"🏆 Забрал на {row_name} ряду!\n"
                    f"+{fmt(res['won'])}{res.get('event', '')}\n"
                    f"📈 x{res['mult']}\n"
                    f"💰 {fmt(res['balance'])}"
                )
                await cb.answer()
                return
            else:
                parts = data.split('_')
                if len(parts) == 4:
                    user_id, r, c = int(parts[1]), int(parts[2]), int(parts[3])
                    if uid != user_id:
                        await cb.answer("❌ Не твоя игра", show_alert=True)
                        return
                    
                    res = core.quack.open(user_id, r, c)
                    
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    
                    if res.get('over'):
                        if res.get('mine'):
                            # Проигрыш
                            kb = []
                            row = res['row_data']
                            row_btns = []
                            for i in range(5):
                                row_btns.append(InlineKeyboardButton(text=row['cells'][i], callback_data="ignore"))
                            kb.append(row_btns)
                            
                            mines_word = "мина" if res['mines_count'] == 1 else "мины"
                            
                            await cb.message.edit_text(
                                f"🐸 КВАК\n\n"
                                f"💥 БУМ! {res['row_idx']} ряд ({res['mines_count']} {mines_word})\n"
                                f"❌ -{fmt(res['bet'])}",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                            )
                        else:
                            # Победа (дошёл до 4 ряда)
                            await cb.message.edit_text(
                                f"🐸 КВАК\n\n"
                                f"🏆 МАКСИМУМ! Все 4 ряда пройдены!\n"
                                f"+{fmt(res['won'])}{res.get('event', '')}\n"
                                f"📈 x{res['mult']}\n"
                                f"💰 {fmt(res['balance'])}"
                            )
                    else:
                        game = core.quack.games.get(user_id)
                        if game:
                            row_text = {0: "первый", 1: "второй", 2: "третий", 3: "четвёртый"}
                            current_row = game['row']
                            mines = core.quack.mines_count[current_row]
                            mines_word = "мина" if mines == 1 else "мины" if mines in [2,3,4] else "мин"
                            
                            await cb.message.edit_text(
                                f"🐸 КВАК | {current_row + 1}/4 | 💣 {mines} {mines_word}\n"
                                f"💰 {fmt(game['bet'])}\n"
                                f"📈 x{res['mult']} | 💎 {fmt(res['won'])}\n\n"
                                f"Клетка ({row_text[current_row]} ряд):",
                                reply_markup=core.quack.kb(user_id, game)
                            )
            await cb.answer()
            return
        
        if data.startswith('pyramid_'):
            if data.startswith('pyramid_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                res = core.pyramid.cashout(user_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(
                    f"🔺 Пирамида\n\n"
                    f"{res['field']}\n"
                    f"🏆 +{fmt(res['won'])}{res.get('event', '')}\n"
                    f"📈 x{res['mult']:.2f}\n"
                    f"🎯 {res['level']}/12\n"
                    f"💰 {fmt(res['balance'])}"
                )
                await cb.answer()
                return
            else:
                parts = data.split('_')
                if len(parts) == 4:
                    user_id, level, cell = int(parts[1]), int(parts[2]), int(parts[3])
                    
                    if uid != user_id:
                        await cb.answer("❌ Не твоя игра", show_alert=True)
                        return
                    
                    res = core.pyramid.open(user_id, level, cell)
                    
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    
                    if res.get('over'):
                        if res.get('win'):
                            await cb.message.edit_text(
                                f"🔺 Пирамида\n\n"
                                f"{res['field']}\n"
                                f"🏆 Максимум!\n"
                                f"+{fmt(res['won'])}{res.get('event', '')}\n"
                                f"📈 x{res['mult']:.2f}\n"
                                f"🎯 {res['level']}/12\n"
                                f"💰 {fmt(res['balance'])}"
                            )
                        else:
                            await cb.message.edit_text(
                                f"🔺 Пирамида\n\n"
                                f"{res['field']}\n"
                                f"💥 Ловушка!\n"
                                f"❌ -{fmt(res['bet'])}\n"
                                f"🎯 {res['level']}/12"
                            )
                    else:
                        game = core.pyramid.games.get(user_id)
                        if game:
                            await cb.message.edit_text(
                                f"🔺 Пирамида | {game['level'] + 1}/12 | 🚪 {game['doors']} двери\n"
                                f"💰 {fmt(game['bet'])}\n"
                                f"📈 x{res['mult']:.2f}\n"
                                f"💎 {fmt(res['won'])}\n\n"
                                f"{res['field']}\n"
                                f"Дверь:",
                                reply_markup=core.pyramid.kb(user_id, game)
                            )
            await cb.answer()
            return
        
        if data.startswith('gold_'):
            if data.startswith('gold_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                res = core.gold.cashout(user_id, chat_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(
                    f"🏆 +{fmt(res['won'])}{res.get('event', '')}\n"
                    f"📈 x{res['mult']}\n"
                    f"🎯 {res['level']}/12\n"
                    f"💰 {fmt(res['balance'])}"
                )
                await cb.answer()
                return
            else:
                side = 1 if 'left' in data else 2
                user_id = int(data.split('_')[2])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                res = core.gold.choose(user_id, side, chat_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                if res.get('max', False):
                    await cb.message.edit_text(
                        f"🏆 Максимум!\n"
                        f"+{fmt(res['won'])}{res.get('event', '')}\n"
                        f"📈 x{res['mult']}\n"
                        f"🎯 {res['level']}/12\n"
                        f"💰 {fmt(res['balance'])}"
                    )
                elif res.get('game_over', False):
                    game_data = {'bet': res['bet'], 'level': res['level'], 'history': [{'level': res['level']+1, 'choice': res['choice'], 'money': res['money'], 'win': False}]}
                    await cb.message.edit_text(core.gold.display(game_data, res))
                else:
                    game = core.gold.games.get(user_id)
                    if game:
                        await cb.message.edit_text(
                            f"{core.gold.display(game, res)}\n\n"
                            f"💰 {fmt(game['bet'])}\n"
                            f"🎯 {game['level']}/12 | 📈 x{res['mult']}\n"
                            f"Сторона:",
                            reply_markup=core.gold.kb(user_id, game)
                        )
            await cb.answer()
            return
        
        if data.startswith('risk_'):
            if data.startswith('risk_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id:
                    await cb.answer("❌ Не твоя игра", show_alert=True)
                    return
                res = core.risk.cashout(user_id, chat_id)
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(
                    f"🏆 +{fmt(res['won'])}{res.get('event', '')}\n"
                    f"📈 x{res['total_mult']:.2f}\n"
                    f"🎯 {res['level']}/3\n"
                    f"💰 {fmt(res['balance'])}"
                )
                await cb.answer()
                return
            elif data.startswith('risk_cell_'):
                parts = data.split('_')
                if len(parts) >= 4:
                    user_id = int(parts[2])
                    idx = int(parts[3])
                    if uid != user_id:
                        await cb.answer("❌ Не твоя игра", show_alert=True)
                        return
                    res = core.risk.open(user_id, idx, chat_id)
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    if res.get('max'):
                        await cb.message.edit_text(
                            f"🏆 Максимум!\n"
                            f"+{fmt(res['won'])}{res.get('event', '')}\n"
                            f"📈 x{res['total_mult']:.2f}\n"
                            f"💰 {fmt(res['balance'])}"
                        )
                    elif res.get('game_over'):
                        await cb.message.edit_text("💥 Мина!")
                    else:
                        game = core.risk.games.get(user_id)
                        if game:
                            await cb.message.edit_text(
                                f"{core.risk.display(game)}\n\n"
                                f"✅ +{fmt(res['won'])}\n\n"
                                f"Клетка:",
                                reply_markup=core.risk.kb(user_id, game)
                            )
            await cb.answer()
            return
        
        if data.startswith('football_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, choice = int(parts[1]), parts[2]
                
                user = core.db.get(uid)
                if user['balance'] < bet:
                    await cb.answer("❌ Не хватает", show_alert=True)
                    return
                
                football_msg = await cb.message.answer_dice(emoji='⚽')
                football_value = football_msg.dice.value
                
                is_goal = football_value >= 4
                result = 'гол' if is_goal else 'мимо'
                win = (choice == 'гол' and is_goal) or (choice == 'мимо' and not is_goal)
                
                if is_goal:
                    result_emoji = '⚽'
                    result_text = f"ГОЛ! [{football_value}]"
                else:
                    result_emoji = '🥅'
                    result_text = f"МИМО [{football_value}]"
                
                if win:
                    win_amount = bet * 2
                    event = core.events.get_active_event()
                    if event and event['name'] == 'money':
                        win_amount *= event['multiplier']
                    
                    core.db.update(uid, balance=user['balance'] - bet + win_amount,
                                  games_played=user.get('games_played',0)+1,
                                  wins=user.get('wins',0)+1)
                    
                    event_text = f" (x{event['multiplier']})" if event and event['name'] == 'money' else ""
                    
                    await cb.message.edit_text(
                        f"⚽ Футбол\n"
                        f"{result_emoji} {result_text}\n"
                        f"✅ Ты выиграл! +{fmt(win_amount)}{event_text}\n"
                        f"💰 {fmt(user['balance'] - bet + win_amount)}"
                    )
                else:
                    core.db.update(uid, balance=user['balance'] - bet,
                                  games_played=user.get('games_played',0)+1)
                    
                    await cb.message.edit_text(
                        f"⚽ Футбол\n"
                        f"{result_emoji} {result_text}\n"
                        f"❌ Ты проиграл! -{fmt(bet)}\n"
                        f"💰 {fmt(user['balance'] - bet)}"
                    )
            await cb.answer()
            return
        
        if data.startswith('basketball_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, choice = int(parts[1]), parts[2]
                
                user = core.db.get(uid)
                if user['balance'] < bet:
                    await cb.answer("❌ Не хватает", show_alert=True)
                    return
                
                basketball_msg = await cb.message.answer_dice(emoji='🏀')
                basketball_value = basketball_msg.dice.value
                
                is_goal = basketball_value >= 4
                result = 'гол' if is_goal else 'мимо'
                win = (choice == 'гол' and is_goal) or (choice == 'мимо' and not is_goal)
                
                if is_goal:
                    result_emoji = '🏀'
                    result_text = f"ГОЛ! [{basketball_value}]"
                else:
                    result_emoji = '🧺'
                    result_text = f"МИМО [{basketball_value}]"
                
                if win:
                    win_amount = bet * 2
                    event = core.events.get_active_event()
                    if event and event['name'] == 'money':
                        win_amount *= event['multiplier']
                    
                    core.db.update(uid, balance=user['balance'] - bet + win_amount,
                                  games_played=user.get('games_played',0)+1,
                                  wins=user.get('wins',0)+1)
                    
                    event_text = f" (x{event['multiplier']})" if event and event['name'] == 'money' else ""
                    
                    await cb.message.edit_text(
                        f"🏀 Баскетбол\n"
                        f"{result_emoji} {result_text}\n"
                        f"✅ Ты выиграл! +{fmt(win_amount)}{event_text}\n"
                        f"💰 {fmt(user['balance'] - bet + win_amount)}"
                    )
                else:
                    core.db.update(uid, balance=user['balance'] - bet,
                                  games_played=user.get('games_played',0)+1)
                    
                    await cb.message.edit_text(
                        f"🏀 Баскетбол\n"
                        f"{result_emoji} {result_text}\n"
                        f"❌ Ты проиграл! -{fmt(bet)}\n"
                        f"💰 {fmt(user['balance'] - bet)}"
                    )
            await cb.answer()
            return
        
        if data.startswith('dart_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, choice = int(parts[1]), parts[2]
                
                user = core.db.get(uid)
                if user['balance'] < bet:
                    await cb.answer("❌ Не хватает", show_alert=True)
                    return
                
                dart_msg = await cb.message.answer_dice(emoji='🎯')
                dart_value = dart_msg.dice.value
                
                if dart_value == 1:
                    result = 'мимо'
                elif dart_value == 2:
                    result = 'красное'
                elif dart_value == 3:
                    result = 'белое'
                elif dart_value == 4:
                    result = 'красное'
                elif dart_value == 5:
                    result = 'белое'
                elif dart_value == 6:
                    result = 'центр'
                
                sector = core.dart.sectors[result]
                win = (choice == result)
                
                if win:
                    win_amount = int(bet * sector['mult'])
                    event = core.events.get_active_event()
                    if event and event['name'] == 'money':
                        win_amount *= event['multiplier']
                    
                    core.db.update(uid, balance=user['balance'] - bet + win_amount,
                                  games_played=user.get('games_played',0)+1,
                                  wins=user.get('wins',0)+1)
                    
                    event_text = f" (x{event['multiplier']})" if event and event['name'] == 'money' else ""
                    multiplier = f"x{sector['mult']}"
                    
                    await cb.message.edit_text(
                        f"🎯 ДАРТС\n\n"
                        f"{sector['emoji']} {sector['name']}! [{dart_value}] {multiplier}\n"
                        f"✅ Ты угадал! +{fmt(win_amount)}{event_text}\n"
                        f"💰 Баланс: {fmt(user['balance'] - bet + win_amount)}"
                    )
                else:
                    core.db.update(uid, balance=user['balance'] - bet,
                                  games_played=user.get('games_played',0)+1)
                    
                    result_text = f"{sector['emoji']} {sector['name']}! [{dart_value}]"
                    if choice == 'мимо':
                        result_text += f" (x{sector['mult']} если бы угадал)"
                    
                    await cb.message.edit_text(
                        f"🎯 ДАРТС\n\n"
                        f"{result_text}\n"
                        f"❌ Ты не угадал! -{fmt(bet)}\n"
                        f"💰 Баланс: {fmt(user['balance'] - bet)}"
                    )
            await cb.answer()
            return
        
        if data.startswith('nft_page_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, page = parts[2], int(parts[3])
                if str(uid) != user_id:
                    await cb.answer("❌ Не твой инвентарь", show_alert=True)
                    return
                await show_nft_list(cb, user_id, page)
            await cb.answer()
            return
        
        if data.startswith('nft_view_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, unique_id = parts[2], '_'.join(parts[3:])
                if str(uid) != user_id:
                    await cb.answer("❌ Не твой NFT", show_alert=True)
                    return
                await show_nft_detail(cb, user_id, unique_id)
            await cb.answer()
            return
        
        if data.startswith('nft_back_'):
            user_id = data.split('_')[2]
            if str(uid) != user_id:
                await cb.answer("❌ Не твой инвентарь", show_alert=True)
                return
            await show_nft_list(cb, user_id, 0)
            await cb.answer()
            return
        
        if data.startswith('nft_sell_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, unique_id = parts[2], '_'.join(parts[3:])
                if str(uid) != user_id:
                    await cb.answer("❌ Не твой NFT", show_alert=True)
                    return
                await state.update_data(sell_nft_id=unique_id)
                await state.set_state(MarketStates.waiting_price)
                await cb.message.edit_text("💰 Цена продажи:")
            await cb.answer()
            return
        
        if data.startswith('nft_transfer_start_'):
            parts = data.split('_')
            if len(parts) >= 5:
                user_id, unique_id = parts[3], '_'.join(parts[4:])
                if str(uid) != user_id:
                    await cb.answer("❌ Не твой NFT", show_alert=True)
                    return
                
                await state.update_data(transfer_nft_id=unique_id)
                await state.set_state(TransferNFTStates.waiting_user)
                await cb.message.edit_text("👤 Введи ID пользователя:")
            await cb.answer()
            return
        
        if data.startswith('transfer_page_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, page = parts[2], int(parts[3])
                if str(uid) != user_id:
                    await cb.answer("❌ Не твой инвентарь", show_alert=True)
                    return
                await show_nft_for_transfer(cb, state, user_id, page)
            await cb.answer()
            return
        
        if data.startswith('transfer_select_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, unique_id = parts[2], '_'.join(parts[3:])
                if str(uid) != user_id:
                    await cb.answer("❌ Не твой NFT", show_alert=True)
                    return
                await process_transfer_nft(cb, state, user_id, unique_id)
            await cb.answer()
            return
        
        if data.startswith('transfer_confirm_'):
            parts = data.split('_')
            if len(parts) >= 4:
                to_uid, unique_id = parts[2], '_'.join(parts[3:])
                await confirm_transfer_nft(cb, state, to_uid, unique_id)
            await cb.answer()
            return
        
        if data == "transfer_cancel":
            await state.clear()
            await cb.message.edit_text("❌ Отменено")
            await cb.answer()
            return
        
        if data.startswith('shop_page_'):
            page = int(data.split('_')[2])
            await show_shop_list(uid, cb, page)
            await cb.answer()
            return
        
        if data.startswith('shop_view_'):
            item_id = data[10:]
            await show_shop_item(cb, item_id)
            await cb.answer()
            return
        
        if data.startswith('shop_buy_'):
            item_id = data[9:]
            res = core.shop.buy(item_id, uid, core.db)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await show_shop_item(cb, item_id)
            await cb.answer()
            return
        
        if data == "shop_back":
            await show_shop_list(uid, cb, 0)
            await cb.answer()
            return
        
        if data.startswith('market_page_'):
            page = int(data.split('_')[2])
            await show_market_list(uid, cb, page)
            await cb.answer()
            return
        
        if data.startswith('market_view_'):
            listing_id = int(data.split('_')[2])
            await show_market_listing(cb, listing_id)
            await cb.answer()
            return
        
        if data.startswith('market_buy_'):
            listing_id = int(data.split('_')[2])
            res = core.market.buy_listing(listing_id, uid)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await show_market_list(uid, cb, 0)
            else:
                await show_market_listing(cb, listing_id)
            await cb.answer()
            return
        
        if data.startswith('market_cancel_'):
            listing_id = int(data.split('_')[2])
            res = core.market.cancel_listing(listing_id, uid)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await show_market_list(uid, cb, 0)
            else:
                await show_market_listing(cb, listing_id)
            await cb.answer()
            return
        
        if data == "market_back":
            await show_market_list(uid, cb, 0)
            await cb.answer()
            return
        
        if data == "market_refresh":
            await show_market_list(uid, cb, 0)
            await cb.answer()
            return
        
        if data.startswith('knb_choice_'):
            if not await state.get_state() == KNBTicTacToe.waiting_choice:
                await cb.answer("❌ Нет игры", show_alert=True)
                return
            
            player_choice = data[11:]
            state_data = await state.get_data()
            
            bet = state_data.get('knb_bet')
            bot_choice = state_data.get('knb_bot_choice')
            player_id = state_data.get('knb_player_id')
            
            if cb.from_user.id != player_id:
                await cb.answer("❌ Не твоя игра", show_alert=True)
                return
            
            result = core.knb.vs_bot(player_choice, bot_choice, bet)
            
            player_emoji = core.knb.get_emoji(player_choice)
            bot_emoji = core.knb.get_emoji(bot_choice)
            
            if result['result'] == 'win':
                current_balance = core.db.get(player_id)['balance']
                core.db.update(player_id, balance=current_balance + result['amount'])
                result_text = result['msg']
            elif result['result'] == 'lose':
                result_text = result['msg']
            else:
                current_balance = core.db.get(player_id)['balance']
                core.db.update(player_id, balance=current_balance + bet)
                result_text = result['msg']
            
            text = (
                f"🪨 КНБ\n\n"
                f"Бот: {bot_emoji} {bot_choice}\n"
                f"Ты: {player_emoji} {player_choice}\n\n"
                f"{result_text}\n"
                f"💰 {fmt(core.db.get(player_id)['balance'])}"
            )
            
            await cb.message.edit_text(text)
            await state.clear()
            await cb.answer()
            return
        
        elif data == "knb_cancel":
            state_data = await state.get_data()
            bet = state_data.get('knb_bet')
            player_id = state_data.get('knb_player_id')
            
            if cb.from_user.id == player_id and bet:
                current_balance = core.db.get(player_id)['balance']
                core.db.update(player_id, balance=current_balance + bet)
                await cb.message.edit_text("❌ Отмена, ставка возвращена")
            else:
                await cb.message.edit_text("❌ Отмена")
            
            await state.clear()
            await cb.answer()
            return
        
        elif data.startswith('knb_join_'):
            duel_id = int(data.split('_')[2])
            duel = core.knb.get_duel(duel_id)
            
            if not duel:
                await cb.answer("❌ Дуэль не найдена", show_alert=True)
                return
            
            opponent_balance = core.db.get(cb.from_user.id)['balance']
            if opponent_balance < duel['bet']:
                await cb.answer(f"❌ Нужно {fmt(duel['bet'])}", show_alert=True)
                return
            
            core.db.update(cb.from_user.id, balance=opponent_balance - duel['bet'])
            
            res = core.knb.join_duel(duel_id, cb.from_user.id)
            
            if not res['ok']:
                if 'Недостаточно средств' not in res.get('msg', ''):
                    core.db.update(cb.from_user.id, balance=core.db.get(cb.from_user.id)['balance'] + duel['bet'])
                await cb.answer(res['msg'], show_alert=True)
                return
            
            await cb.message.edit_text(
                f"⚔️ Дуэль\n\n"
                f"👤 Создатель: {(await cb.bot.get_chat(duel['creator_id'])).first_name}\n"
                f"👤 Противник: {cb.from_user.first_name}\n"
                f"💰 {fmt(duel['bet'])}\n\n"
                f"Ожидаем выбор создателя..."
            )
            
            creator_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🪨 Камень", callback_data=f"knb_duel_choice_{duel_id}_камень"),
                    InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"knb_duel_choice_{duel_id}_ножницы"),
                    InlineKeyboardButton(text="📄 Бумага", callback_data=f"knb_duel_choice_{duel_id}_бумага")
                ],
                [InlineKeyboardButton(text="❌ Отменить", callback_data=f"knb_cancel_duel_{duel_id}")]
            ])
            
            await cb.bot.send_message(
                duel['chat_id'],
                f"⚔️ {cb.from_user.first_name} принял вызов!\n\n"
                f"👤 Создатель: {(await cb.bot.get_chat(duel['creator_id'])).first_name}\n"
                f"💰 {fmt(duel['bet'])}\n\n"
                f"Твой выбор:",
                reply_markup=creator_kb
            )
            await cb.answer()
            return
        
        elif data.startswith('knb_duel_choice_'):
            parts = data.split('_')
            if len(parts) >= 5:
                duel_id = int(parts[3])
                choice = parts[4]
                
                duel = core.knb.get_duel(duel_id)
                
                if not duel:
                    await cb.answer("❌ Дуэль не найдена", show_alert=True)
                    return
                
                if cb.from_user.id != duel['creator_id']:
                    await cb.answer("❌ Не твоя дуэль", show_alert=True)
                    return
                
                res = core.knb.make_choice(duel_id, cb.from_user.id, choice)
                
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                
                await cb.message.edit_text("✅ Выбор принят, ждём противника...")
                
                if res.get('next') == 'opponent':
                    opponent_kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🪨 Камень", callback_data=f"knb_duel_opponent_{duel_id}_камень"),
                            InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"knb_duel_opponent_{duel_id}_ножницы"),
                            InlineKeyboardButton(text="📄 Бумага", callback_data=f"knb_duel_opponent_{duel_id}_бумага")
                        ],
                        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"knb_cancel_duel_{duel_id}")]
                    ])
                    
                    await cb.bot.send_message(
                        duel['chat_id'],
                        f"⚔️ Создатель сделал выбор!\n\n"
                        f"👤 Противник: {(await cb.bot.get_chat(duel['opponent_id'])).first_name}\n"
                        f"💰 {fmt(duel['bet'])}\n\n"
                        f"Твой выбор:",
                        reply_markup=opponent_kb
                    )
            await cb.answer()
            return
        
        elif data.startswith('knb_duel_opponent_'):
            parts = data.split('_')
            if len(parts) >= 5:
                duel_id = int(parts[3])
                choice = parts[4]
                
                duel = core.knb.get_duel(duel_id)
                
                if not duel:
                    await cb.answer("❌ Дуэль не найдена", show_alert=True)
                    return
                
                if cb.from_user.id != duel['opponent_id']:
                    await cb.answer("❌ Не твоя дуэль", show_alert=True)
                    return
                
                res = core.knb.make_choice(duel_id, cb.from_user.id, choice)
                
                if not res['ok']:
                    await cb.answer(res['msg'], show_alert=True)
                    return
                
                creator_emoji = core.knb.get_emoji(duel['creator_choice'])
                opponent_emoji = core.knb.get_emoji(duel['opponent_choice'])
                
                result_text = res['result_msg']
                
                if res['winner'] == 'draw':
                    core.db.update(duel['creator_id'], balance=core.db.get(duel['creator_id'])['balance'] + duel['bet'])
                    core.db.update(duel['opponent_id'], balance=core.db.get(duel['opponent_id'])['balance'] + duel['bet'])
                elif res['winner'] == duel['creator_id']:
                    core.db.update(duel['creator_id'], balance=core.db.get(duel['creator_id'])['balance'] + duel['bet'] * 2)
                else:
                    core.db.update(duel['opponent_id'], balance=core.db.get(duel['opponent_id'])['balance'] + duel['bet'] * 2)
                
                result_text_full = (
                    f"⚔️ Результат\n\n"
                    f"👤 Создатель: {creator_emoji} {duel['creator_choice']}\n"
                    f"👤 Противник: {opponent_emoji} {duel['opponent_choice']}\n\n"
                    f"{result_text}"
                )
                
                await cb.bot.send_message(duel['chat_id'], result_text_full)
                await cb.message.edit_text("✅ Готово, результат в чате")
                
                core.knb.delete_duel(duel_id)
            await cb.answer()
            return
        
        elif data.startswith('knb_cancel_duel_'):
            duel_id = int(data.split('_')[3])
            duel = core.knb.get_duel(duel_id)
            
            if not duel:
                await cb.answer("❌ Дуэль не найдена", show_alert=True)
                return
            
            if cb.from_user.id == duel['creator_id'] or cb.from_user.id == duel.get('opponent_id'):
                if duel['status'] == 'waiting':
                    core.db.update(duel['creator_id'], balance=core.db.get(duel['creator_id'])['balance'] + duel['bet'])
                elif duel['status'] == 'creator_choice' and duel.get('opponent_id'):
                    core.db.update(duel['creator_id'], balance=core.db.get(duel['creator_id'])['balance'] + duel['bet'])
                    core.db.update(duel['opponent_id'], balance=core.db.get(duel['opponent_id'])['balance'] + duel['bet'])
                
                await cb.bot.send_message(duel['chat_id'], f"❌ Дуэль отменена, ставки возвращены")
                core.knb.delete_duel(duel_id)
                await cb.answer("✅ Отменено")
            else:
                await cb.answer("❌ Нельзя", show_alert=True)
            return
        
        if data.startswith('ad_subs_'):
            await process_ad_subs_callback(cb, state)
            return
        
        if data.startswith('ad_reward_'):
            await process_ad_reward_callback(cb, state)
            return
        
        if data == "ad_confirm":
            await process_ad_confirm(cb, state)
            return
        
        if data == "ad_cancel":
            await process_ad_cancel(cb, state)
            return
        
        if data.startswith('do_task_'):
            await process_do_task(cb, state)
            return
        
        if data.startswith('check_sub_'):
            await process_check_sub(cb, state)
            return
        
        if data.startswith('stop_ad_'):
            await process_stop_ad(cb, state)
            return
        
        if data == "logs_stats":
            if not is_admin(uid):
                await cb.answer("❌ Только для админов", show_alert=True)
                return
            
            stats = core.logs.get_stats()
            
            text = (
                "📊 СТАТИСТИКА ЛОГОВ\n\n"
                f"📝 Всего действий: {stats['total_actions']}\n"
                f"⏰ За 24 часа: {stats['last_24h']}\n"
                f"💰 Выдано всего: {fmt(stats['total_given'])}\n"
                f"💸 Забрано всего: {fmt(stats['total_taken'])}\n"
                f"⛔ Забанено: {stats['total_bans']}\n\n"
                f"📈 По действиям:\n"
            )
            
            for action, count in stats['by_action'].items():
                action_emoji = {
                    "give": "💰", "take": "💸", "ban": "⛔", "unban": "✅",
                    "make_admin": "👑", "remove_admin": "👤", "create_promo": "🎫",
                    "give_status": "⭐", "create_nft": "🖼️", "clear_logs": "🧹",
                    "give_bank": "💳", "take_bank": "💳", "event_start": "🎉",
                    "event_end": "⏰", "toggle_status": "⚙️", "create_ad": "📢"
                }.get(action, "🔹")
                text += f"{action_emoji} {action}: {count}\n"
            
            text += f"\n👤 По админам:\n"
            
            for admin, count in stats['by_admin'].items():
                try:
                    admin_chat = await cb.bot.get_chat(int(admin))
                    admin_name = admin_chat.first_name
                except:
                    admin_name = f"ID {admin}"
                text += f"👤 {admin_name}: {count}\n"
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад к логам", callback_data="logs_back")]
            ])
            
            await cb.message.edit_text(text, reply_markup=kb)
            await cb.answer()
            return
        
        if data == "logs_clear":
            if not is_creator(uid):
                await cb.answer("❌ Только создатель может очистить логи", show_alert=True)
                return
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, очистить", callback_data="logs_clear_confirm")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="logs_back")]
            ])
            
            await cb.message.edit_text(
                "⚠️ ТОЧНО ОЧИСТИТЬ ВСЕ ЛОГИ?\n\n"
                "Это действие нельзя отменить!",
                reply_markup=kb
            )
            await cb.answer()
            return
        
        if data == "logs_clear_confirm":
            if not is_creator(uid):
                await cb.answer("❌ Только создатель", show_alert=True)
                return
            
            core.logs.clear_logs()
            
            core.logs.add_log(
                admin_id=uid,
                action="clear_logs",
                details="Очистил все логи"
            )
            
            await cb.message.edit_text("✅ Все логи очищены")
            await cb.answer()
            return
        
        if data == "logs_back" or data == "logs_all":
            logs = core.logs.get_logs(limit=50)
            title = "📋 Все логи админов"
            
            if not logs:
                await cb.message.edit_text(f"{title}\n\n📭 Логов нет")
                await cb.answer()
                return
            
            text = core.logs.format_logs(logs, detailed=True)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📊 Статистика", callback_data="logs_stats"),
                    InlineKeyboardButton(text="🧹 Очистить логи", callback_data="logs_clear")
                ],
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="logs_refresh")]
            ])
            
            await cb.message.edit_text(f"{title}\n\n{text}", reply_markup=kb)
            await cb.answer()
            return
        
        if data == "logs_refresh":
            logs = core.logs.get_logs(limit=50)
            title = "📋 Все логи админов"
            
            if not logs:
                await cb.message.edit_text(f"{title}\n\n📭 Логов нет")
                await cb.answer()
                return
            
            text = core.logs.format_logs(logs, detailed=True)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📊 Статистика", callback_data="logs_stats"),
                    InlineKeyboardButton(text="🧹 Очистить логи", callback_data="logs_clear")
                ],
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="logs_refresh")]
            ])
            
            await cb.message.edit_text(f"{title}\n\n{text}", reply_markup=kb)
            await cb.answer()
            return
        
        if data.startswith('bank_') or data.startswith('close_deposit_') or data.startswith('pay_loan_'):
            if data == "bank_card":
                b = core.bank.get(uid)
                kb = [
                    [InlineKeyboardButton(text="💰 Положить", callback_data="bank_card_deposit"),
                     InlineKeyboardButton(text="💸 Снять", callback_data="bank_card_withdraw")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]
                ]
                await cb.message.edit_text(
                    f"💳 Карта\n\n{fmt(b['card_balance'])}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                )
                await cb.answer()
                return
            
            elif data == "bank_card_deposit":
                await state.set_state(BankStates.waiting_card_amount)
                await state.update_data(bank_action='deposit')
                await cb.message.edit_text("💰 Сумма:")
                await cb.answer()
                return
            
            elif data == "bank_card_withdraw":
                await state.set_state(BankStates.waiting_card_amount)
                await state.update_data(bank_action='withdraw')
                await cb.message.edit_text("💸 Сумма:")
                await cb.answer()
                return
            
            elif data == "bank_deposits":
                b = core.bank.get(uid)
                active = [d for d in b['deposits'] if d['status'] == 'active']
                
                if not active:
                    kb = [[InlineKeyboardButton(text="➕ Открыть", callback_data="bank_new_deposit")],
                          [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]]
                    await cb.message.edit_text("📭 Нет вкладов", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
                    await cb.answer()
                    return
                
                text = "📈 Вклады\n\n"
                kb = []
                
                for d in active:
                    end = datetime.datetime.fromisoformat(d['end_date'])
                    left = (end - datetime.datetime.now()).days
                    text += f"{d['id'][-8:]}\n💰 {fmt(d['amount'])} | 📈 {d['rate']}%\n⏰ {left} дн.\n\n"
                    kb.append([InlineKeyboardButton(text=f"❌ Закрыть {d['id'][-8:]}", callback_data=f"close_deposit_{d['id']}")])
                
                kb.append([InlineKeyboardButton(text="➕ Новый", callback_data="bank_new_deposit")])
                kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
                
                await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
                await cb.answer()
                return
            
            elif data == "bank_new_deposit":
                await state.set_state(BankStates.waiting_deposit_amount)
                await cb.message.edit_text("💰 Сумма вклада:")
                await cb.answer()
                return
            
            elif data == "bank_loans":
                b = core.bank.get(uid)
                active = [l for l in b['loans'] if l['status'] == 'active']
                
                if not active:
                    kb = [[InlineKeyboardButton(text="💰 Взять", callback_data="bank_new_loan")],
                          [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]]
                    await cb.message.edit_text("📭 Нет кредитов", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
                    await cb.answer()
                    return
                
                text = "📉 Кредиты\n\n"
                kb = []
                
                for l in active:
                    end = datetime.datetime.fromisoformat(l['end_date'])
                    left = (end - datetime.datetime.now()).days
                    percent = int((l['total_to_return'] - l['amount']) / l['amount'] * 100)
                    
                    text += f"{l['id'][-8:]}\n"
                    text += f"💰 {fmt(l['amount'])} | 📈 {percent}%\n"
                    text += f"💵 Осталось {fmt(l['remaining'])} | ⏰ {left} дн.\n\n"
                    
                    kb.append([InlineKeyboardButton(text=f"💸 Оплатить {fmt(l['remaining'])}", callback_data=f"pay_loan_{l['id']}")])
                
                kb.append([InlineKeyboardButton(text="💰 Новый", callback_data="bank_new_loan")])
                kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
                
                await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
                await cb.answer()
                return
            
            elif data == "bank_new_loan":
                await state.set_state(BankStates.waiting_loan_amount)
                await cb.message.edit_text(f"💰 Сумма кредита (макс {fmt(core.bank.settings.read()['max_loan_amount'])}):")
                await cb.answer()
                return
            
            elif data == "bank_help":
                kb = [[InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]]
                await cb.message.edit_text(
                    "🏦 Банк\n\n"
                    "💳 Карта - деньги в безопасности\n"
                    "📈 Вклады - % за срок\n"
                    "  7д +3% | 14д +4.5% | 30д +6%\n"
                    "  90д +8% | 180д +10% | 365д +12%\n\n"
                    "📉 Кредиты - займы\n"
                    "  Макс 1кк, можно 1 кредит",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                )
                await cb.answer()
                return
            
            elif data == "bank_back":
                await cmd_bank(cb.message)
                await cb.answer()
                return
            
            elif data.startswith("close_deposit_"):
                dep_id = data[14:]
                res = core.bank.close_deposit(uid, dep_id)
                if res['ok']:
                    user = core.db.get(uid)
                    core.db.update(uid, balance=user['balance'] + res['amount'])
                    await cb.answer("✅ Вклад закрыт", show_alert=True)
                    await callback_handler(cb.with_data("bank_deposits"), state)
                else:
                    await cb.answer(res['msg'], show_alert=True)
                return
            
            elif data.startswith("pay_loan_"):
                loan_id = data[9:]
                loan = None
                b = core.bank.get(uid)
                for l in b['loans']:
                    if l['id'] == loan_id:
                        loan = l
                        break
                
                if loan:
                    await state.update_data(pay_loan_id=loan_id)
                    await state.set_state(BankStates.waiting_loan_payment)
                    await cb.message.edit_text(f"💸 Сумма (осталось {fmt(loan['remaining'])}):")
                else:
                    await cb.answer("❌ Не найден", show_alert=True)
                await cb.answer()
                return
        
        if data == "profile_bonus":
            res = core.status.get_bonus(uid, core.db)
            await cb.message.reply(res['msg'])
            await cb.answer()
            return
        
        if data == "profile_top":
            await cmd_top(cb.message)
            await cb.answer()
            return
        
        if data == "profile_total":
            uid = str(cb.from_user.id)
            user = core.db.get(uid)
            bank = core.bank.get(uid)
            total = user['balance'] + bank['card_balance']
            
            text = (
                f"💎 ОБЩИЙ БАЛАНС\n\n"
                f"💰 Наличные: {fmt(user['balance'])}\n"
                f"💳 На карте: {fmt(bank['card_balance'])}\n"
                f"{'═' * 20}\n"
                f"💎 ВСЕГО: {fmt(total)}"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ])
            
            await cb.message.edit_text(text, reply_markup=kb)
            await cb.answer()
            return
        
        if data == "bank_menu":
            await cmd_bank(cb.message)
            await cb.answer()
            return
        
        if data.startswith('emoji_'):
            if data == "emoji_custom":
                await state.set_state(AdminStates.waiting_nft_emoji)
                await cb.message.edit_text("Введи эмодзи:")
            else:
                emoji = data[6:]
                await finish_nft_creation(cb.message, state, emoji)
            await cb.answer()
            return
        
        await cb.answer()
    except Exception as e:
        print(f"Ошибка: {e}")
        await cb.answer("❌ Ошибка", show_alert=True)

async def handle_bank_card_amount(msg: Message, state: FSMContext):
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.reply("❌ Отменено")
        return
    
    data = await state.get_data()
    action = data.get('bank_action')
    
    u = core.db.get(msg.from_user.id)
    amount = core.parse_bet(msg.text, u['balance'])
    
    if amount <= 0:
        await msg.reply("❌ Сумма > 0")
        return
    
    if action == 'deposit':
        if u['balance'] < amount:
            await msg.reply(f"❌ Не хватает, баланс {fmt(u['balance'])}")
            return
        res = core.bank.card_deposit(msg.from_user.id, amount, u['balance'])
        if res['ok']:
            core.db.update(msg.from_user.id, balance=u['balance'] - amount)
    
    elif action == 'withdraw':
        res = core.bank.card_withdraw(msg.from_user.id, amount, u['balance'])
        if res['ok']:
            core.db.update(msg.from_user.id, balance=u['balance'] + amount)
    
    await msg.reply(res['msg'])
    await state.clear()
    await cmd_bank(msg)

async def handle_deposit_amount(msg: Message, state: FSMContext):
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.reply("❌ Отменено")
        return
    
    u = core.db.get(msg.from_user.id)
    amount = core.parse_bet(msg.text, u['balance'])
    
    if amount <= 0:
        await msg.reply("❌ Сумма > 0")
        return
    
    if u['balance'] < amount:
        await msg.reply(f"❌ Не хватает, баланс {fmt(u['balance'])}")
        return
    
    await state.update_data(deposit_amount=amount)
    await state.set_state(BankStates.waiting_deposit_days)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7д 3%", callback_data="deposit_days_7"),
         InlineKeyboardButton(text="14д 4.5%", callback_data="deposit_days_14")],
        [InlineKeyboardButton(text="30д 6%", callback_data="deposit_days_30"),
         InlineKeyboardButton(text="90д 8%", callback_data="deposit_days_90")],
        [InlineKeyboardButton(text="180д 10%", callback_data="deposit_days_180"),
         InlineKeyboardButton(text="365д 12%", callback_data="deposit_days_365")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="bank_back")]
    ])
    
    await msg.reply(f"💰 {fmt(amount)}\nСрок:", reply_markup=kb)

async def handle_loan_amount(msg: Message, state: FSMContext):
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.reply("❌ Отменено")
        return
    
    u = core.db.get(msg.from_user.id)
    amount = core.parse_bet(msg.text)
    
    if amount <= 0:
        await msg.reply("❌ Сумма > 0")
        return
    
    max_loan = core.bank.settings.read()['max_loan_amount']
    if amount > max_loan:
        await msg.reply(f"❌ Макс {fmt(max_loan)}")
        return
    
    await state.update_data(loan_amount=amount)
    await state.set_state(BankStates.waiting_loan_days)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7д 5%", callback_data="loan_days_7"),
         InlineKeyboardButton(text="14д 7%", callback_data="loan_days_14")],
        [InlineKeyboardButton(text="30д 10%", callback_data="loan_days_30"),
         InlineKeyboardButton(text="90д 12%", callback_data="loan_days_90")],
        [InlineKeyboardButton(text="180д 15%", callback_data="loan_days_180"),
         InlineKeyboardButton(text="365д 20%", callback_data="loan_days_365")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="bank_back")]
    ])
    
    await msg.reply(f"💰 {fmt(amount)}\nСрок:", reply_markup=kb)

async def handle_loan_payment(msg: Message, state: FSMContext):
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.reply("❌ Отменено")
        return
    
    data = await state.get_data()
    loan_id = data.get('pay_loan_id')
    if not loan_id:
        await state.clear()
        return
    
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(msg.text, u['balance'])
    
    if a <= 0:
        await msg.reply("❌ Сумма > 0")
        return
    
    res = core.bank.pay_loan(msg.from_user.id, loan_id, a, u['balance'])
    if res['ok']:
        core.db.update(msg.from_user.id, balance=u['balance'] - a)
        await msg.reply(res['msg'])
        await state.clear()
        await cmd_loans(msg)
    else:
        await msg.reply(res['msg'])

async def handle_russian(msg: Message, state: FSMContext):
    text = msg.text.lower().strip()
    
    class FC:
        def __init__(self, a):
            self.args = a
        def __bool__(self):
            return self.args is not None
    
    if text in ['баланс', 'б']:
        await cmd_balance(msg)
    elif text in ['профиль', 'проф', 'п']:
        await cmd_profile(msg)
    elif text in ['помощь', 'help', 'команды']:
        await cmd_help(msg)
    elif text == 'топ':
        await cmd_top(msg)
    elif text == 'банк':
        await cmd_bank(msg)
    elif text == 'карта':
        await cmd_card(msg)
    elif text == 'вклады':
        await cmd_deposits(msg)
    elif text == 'кредиты':
        await cmd_loans(msg)
    elif text == 'создать промо':
        await cmd_create_promo(msg, state)
    elif text == 'мои промо':
        await cmd_my_promos(msg)
    elif text == 'игры':
        await cmd_games(msg)
    elif text == '/cancel_game' or text == 'отмена':
        await cmd_cancel_game(msg)
    elif text == 'статус':
        await cmd_status(msg)
    elif text == 'бонус':
        await cmd_bonus(msg)
    elif text == 'ид' and msg.reply_to_message:
        await cmd_id(msg)
    elif text.startswith('админы') and is_admin(msg.from_user.id):
        await cmd_admins(msg)
    elif text.startswith('назначить') and msg.reply_to_message and is_creator(msg.from_user.id):
        await cmd_make_admin(msg)
    elif text.startswith('снять') and msg.reply_to_message and is_creator(msg.from_user.id):
        await cmd_remove_admin(msg)
    elif text.startswith('блок ') or text == 'блок':
        await cmd_block(msg, state)
    elif text.startswith('разблок ') or text == 'разблок':
        await cmd_unblock(msg)
    elif text == '/cancel' or text == 'отмена':
        await cmd_cancel_transfer(msg, state)
    elif text in ['мои нфт', 'инвентарь']:
        await cmd_my_nft(msg)
    elif text in ['нфт', 'магазин']:
        await cmd_nft_shop(msg)
    elif text == 'рынок':
        await cmd_market(msg)
    elif text.startswith('передать нфт '):
        await cmd_transfer_nft_start(msg, state)
    elif text == 'реклама':
        await cmd_ad_start(msg, state)
    elif text == 'заработать':
        await cmd_earn(msg)
    elif text == 'мои задания' or text == 'мои рекламы':
        await cmd_my_ads(msg)
    elif text.startswith('проверка_канала') and is_admin(msg.from_user.id):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            await cmd_check_channel(msg, CommandObject(args=parts[1]))
        else:
            await cmd_check_channel(msg, CommandObject(args=''))
    elif text.startswith('ивент ') and is_creator(msg.from_user.id):
        parts = text.split()
        if len(parts) >= 3:
            await cmd_event_start(msg, CommandObject(args=f"{parts[1]} {parts[2]}"))
        else:
            await msg.reply("❌ ивент [название] [секунды]\nпример: ивент money 60")
    elif text == 'ивент статус':
        await cmd_event_status(msg)
    elif text == 'ивент стоп' and is_creator(msg.from_user.id):
        await cmd_event_end(msg)
    elif text == 'ивент история' and is_admin(msg.from_user.id):
        await cmd_event_history(msg)
    elif text.startswith('логи') and is_admin(msg.from_user.id):
        await cmd_logs(msg)
    elif text.startswith('топ общий') and is_admin(msg.from_user.id):
        await cmd_top_total(msg)
    elif text.startswith('выдать статус ') and msg.reply_to_message and is_creator(msg.from_user.id):
        await cmd_give_status(msg)
    elif text == 'список статусов' and is_creator(msg.from_user.id):
        await cmd_status_list(msg)
    
    elif text.startswith('положить '):
        p = text.split()
        await cmd_deposit(msg, FC(p[1] if len(p) > 1 else None))
    elif text.startswith('снять '):
        p = text.split()
        await cmd_withdraw(msg, FC(p[1] if len(p) > 1 else None))
    elif text.startswith('вклад '):
        p = text.split()
        if len(p) >= 3:
            await cmd_create_deposit(msg, FC(f"{p[1]} {p[2]}"))
        else:
            await msg.reply("❌ вклад [сумма] [дни]")
    elif text.startswith('кредит '):
        p = text.split()
        if len(p) >= 3:
            await cmd_create_loan(msg, FC(f"{p[1]} {p[2]}"))
        else:
            await msg.reply("❌ кредит [сумма] [дни]")
    elif text.startswith('монетка'):
        p = text.split()
        if len(p) > 1:
            await cmd_coin(msg, FC(' '.join(p[1:])))
        else:
            await cmd_coin(msg, FC(None))
    elif text.startswith('слоты'):
        p = text.split()
        if len(p) > 1:
            await cmd_slots(msg, FC(p[1]))
        else:
            await cmd_slots(msg, FC(None))
    elif text.startswith('кубик'):
        p = text.split()
        if len(p) > 1:
            await cmd_dice(msg, FC(' '.join(p[1:])))
        else:
            await cmd_dice(msg, FC(None))
    elif text.startswith('краш'):
        p = text.split()
        if len(p) > 1:
            await cmd_crash(msg, FC(' '.join(p[1:])))
        else:
            await cmd_crash(msg, FC(None))
    elif text.startswith('мины'):
        p = text.split()
        if len(p) > 1:
            await cmd_mines(msg, FC(' '.join(p[1:])))
        else:
            await cmd_mines(msg, FC(None))
    elif text.startswith('башня'):
        p = text.split()
        if len(p) > 1:
            await cmd_tower(msg, FC(' '.join(p[1:])))
        else:
            await cmd_tower(msg, FC(None))
    elif text.startswith('алмазы'):
        p = text.split()
        if len(p) > 1:
            await cmd_diamonds(msg, CommandObject(args=' '.join(p[1:])))
        else:
            await cmd_diamonds(msg, CommandObject(args=None))
    elif text.startswith('квак'):
        p = text.split()
        if len(p) > 1:
            await cmd_quack(msg, CommandObject(args=' '.join(p[1:])))
        else:
            await cmd_quack(msg, CommandObject(args=None))
    elif text.startswith('пирамида'):
        p = text.split()
        if len(p) > 1:
            await cmd_pyramid(msg, CommandObject(args=' '.join(p[1:])))
        else:
            await cmd_pyramid(msg, CommandObject(args=None))
    elif text.startswith('рулетка') or text.startswith('рул'):
        p = text.split()
        if len(p) > 1:
            await cmd_roulette(msg, FC(' '.join(p[1:])))
        else:
            await cmd_roulette(msg, FC(None))
    elif text.startswith('золото'):
        p = text.split()
        if len(p) > 1:
            await cmd_gold(msg, FC(p[1]))
        else:
            await cmd_gold(msg, FC(None))
    elif text.startswith('риск'):
        p = text.split()
        if len(p) > 1:
            await cmd_risk(msg, FC(p[1]))
        else:
            await cmd_risk(msg, FC(None))
    elif text.startswith('футбол'):
        p = text.split()
        if len(p) > 1:
            await cmd_football(msg, CommandObject(args=' '.join(p[1:])))
        else:
            await cmd_football(msg, CommandObject(args=None))
    elif text.startswith('бс') or text.startswith('баскетбол'):
        p = text.split()
        if len(p) > 1:
            await cmd_basketball(msg, CommandObject(args=' '.join(p[1:])))
        else:
            await cmd_basketball(msg, CommandObject(args=None))
    elif text.startswith('дартс'):
        p = text.split()
        if len(p) > 1:
            await cmd_dart(msg, CommandObject(args=' '.join(p[1:])))
        else:
            await cmd_dart(msg, CommandObject(args=None))
    elif text.startswith('промо '):
        code = text[6:].strip().upper()
        await cmd_promo(msg, CommandObject(args=code))
    elif text.startswith('кнб '):
        parts = text.split(maxsplit=1)
        await cmd_knb(msg, CommandObject(args=parts[1] if len(parts) > 1 else ''), state)
    elif text.startswith('дуэль кнб '):
        parts = text.split(maxsplit=2)
        await cmd_knb_duel(msg, CommandObject(args=parts[2] if len(parts) > 2 else ''), state)
    elif text.startswith('дать ') or text.startswith('дай '):
        await cmd_give(msg)
    elif text.startswith('выдать '):
        await cmd_admin_give(msg)
    elif text.startswith('забрать '):
        await cmd_admin_take(msg)

async def main():
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Попытка {attempt + 1}/{max_retries}...")
            
            bot = Bot(token=BOT_TOKEN)
            
            await bot.get_me()
            print("✅ Подключено")
            
            dp = Dispatcher(storage=MemoryStorage())
            
            dp.message.middleware.register(ban_middleware)
            
            dp.message.register(cmd_start, CommandStart())
            dp.message.register(cmd_help, Command("help"))
            dp.message.register(cmd_help, Command("помощь"))
            dp.message.register(cmd_games, Command("games"))
            dp.message.register(cmd_games, Command("игры"))
            dp.message.register(cmd_cancel_game, Command("cancel_game"))
            dp.message.register(cmd_cancel_game, Command("отмена"))
            
            dp.message.register(cmd_profile, Command("profile"))
            dp.message.register(cmd_profile, Command("профиль"))
            dp.message.register(cmd_profile, Command("п"))
            
            dp.message.register(cmd_balance, Command("balance"))
            dp.message.register(cmd_balance, Command("б"))
            dp.message.register(cmd_balance, Command("баланс"))
            
            dp.message.register(cmd_bonus, Command("bonus"))
            dp.message.register(cmd_bonus, Command("бонус"))
            
            dp.message.register(cmd_status, Command("status"))
            dp.message.register(cmd_status, Command("статус"))
            
            dp.message.register(cmd_top, Command("top"))
            dp.message.register(cmd_top, Command("топ"))
            
            dp.message.register(cmd_bank, Command("bank"))
            dp.message.register(cmd_bank, Command("банк"))
            
            dp.message.register(cmd_card, Command("card"))
            dp.message.register(cmd_card, Command("карта"))
            
            dp.message.register(cmd_deposits, Command("deposits"))
            dp.message.register(cmd_deposits, Command("вклады"))
            
            dp.message.register(cmd_loans, Command("loans"))
            dp.message.register(cmd_loans, Command("кредиты"))
            
            dp.message.register(cmd_create_promo, Command("create_promo"))
            dp.message.register(cmd_create_promo, Command("создать_промо"))
            
            dp.message.register(cmd_my_promos, Command("my_promos"))
            dp.message.register(cmd_my_promos, Command("мои_промо"))
            
            dp.message.register(cmd_promo, Command("promo"))
            dp.message.register(cmd_promo, Command("промо"))
            
            dp.message.register(cmd_id, Command("id"))
            dp.message.register(cmd_id, Command("ид"))
            
            dp.message.register(cmd_admins, Command("admins"))
            dp.message.register(cmd_admins, Command("админы"))
            
            dp.message.register(cmd_make_admin, Command("make_admin"))
            dp.message.register(cmd_make_admin, Command("назначить"))
            
            dp.message.register(cmd_remove_admin, Command("remove_admin"))
            dp.message.register(cmd_remove_admin, Command("снять"))
            
            dp.message.register(cmd_block, Command("block"))
            dp.message.register(cmd_block, Command("блок"))
            
            dp.message.register(cmd_unblock, Command("unblock"))
            dp.message.register(cmd_unblock, Command("разблок"))
            
            dp.message.register(cmd_cancel_transfer, Command("cancel"))
            
            # NFT команды
            dp.message.register(cmd_my_nft, Command("my_nft"))
            dp.message.register(cmd_my_nft, Command("мои_нфт"))
            dp.message.register(cmd_my_nft, Command("инвентарь"))
            
            dp.message.register(cmd_nft_shop, Command("nft_shop"))
            dp.message.register(cmd_nft_shop, Command("нфт"))
            dp.message.register(cmd_nft_shop, Command("магазин"))
            
            dp.message.register(cmd_market, Command("market"))
            dp.message.register(cmd_market, Command("рынок"))
            
            dp.message.register(cmd_transfer_nft_start, Command("transfer_nft"))
            dp.message.register(cmd_transfer_nft_start, Command("передать_нфт"))
            
            dp.message.register(cmd_create_nft, Command("create_nft"))
            dp.message.register(cmd_create_nft, Command("создать_нфт"))
            
            dp.message.register(cmd_all_nft, Command("all_nft"))
            dp.message.register(cmd_all_nft, Command("все_нфт"))
            
            # Рекламные задания
            dp.message.register(cmd_ad_start, Command("ad"))
            dp.message.register(cmd_ad_start, Command("реклама"))
            
            dp.message.register(cmd_earn, Command("earn"))
            dp.message.register(cmd_earn, Command("заработать"))
            
            dp.message.register(cmd_my_ads, Command("my_ads"))
            dp.message.register(cmd_my_ads, Command("мои_задания"))
            
            dp.message.register(cmd_check_channel, Command("check_channel"))
            dp.message.register(cmd_check_channel, Command("проверка_канала"))
            
            # Ивент команды
            dp.message.register(cmd_event_start, Command("event_start"))
            dp.message.register(cmd_event_start, Command("ивент"))
            
            dp.message.register(cmd_event_status, Command("event_status"))
            dp.message.register(cmd_event_status, Command("ивент_статус"))
            
            dp.message.register(cmd_event_end, Command("event_end"))
            dp.message.register(cmd_event_end, Command("ивент_стоп"))
            
            dp.message.register(cmd_event_history, Command("event_history"))
            dp.message.register(cmd_event_history, Command("ивент_история"))
            
            # Игровые команды
            for cmd in ['deposit', 'withdraw', 'create_deposit', 'create_loan', 'coin', 'slots',
                        'dice', 'crash', 'mines', 'tower', 'diamonds', 'quack', 'pyramid', 'roulette', 
                        'gold', 'risk', 'football', 'basketball', 'dart', 'knb', 'knb_duel', 'give']:
                dp.message.register(globals()[f"cmd_{cmd}"], Command(cmd))
            
            dp.message.register(cmd_admin_give, Command("give"))
            dp.message.register(cmd_admin_take, Command("take"))
            
            dp.message.register(process_promo, PromoStates.waiting_reward)
            dp.message.register(process_promo, PromoStates.waiting_limit)
            dp.message.register(handle_loan_payment, BankStates.waiting_loan_payment)
            dp.message.register(handle_market_price, MarketStates.waiting_price)
            dp.message.register(handle_transfer_user_input, TransferNFTStates.waiting_user)
            dp.message.register(handle_bank_card_amount, BankStates.waiting_card_amount)
            dp.message.register(handle_deposit_amount, BankStates.waiting_deposit_amount)
            dp.message.register(handle_loan_amount, BankStates.waiting_loan_amount)
            
            dp.message.register(process_nft_id, AdminStates.waiting_nft_id)
            dp.message.register(process_nft_name, AdminStates.waiting_nft_name)
            dp.message.register(process_nft_price, AdminStates.waiting_nft_price)
            dp.message.register(process_nft_quantity, AdminStates.waiting_nft_quantity)
            dp.message.register(process_nft_description, AdminStates.waiting_nft_description)
            dp.message.register(process_nft_emoji, AdminStates.waiting_nft_emoji)
            
            dp.message.register(process_ad_channel, AdStates.waiting_channel)
            dp.message.register(process_ad_subs_custom, AdStates.waiting_subscribers)
            dp.message.register(process_ad_reward_custom, AdStates.waiting_reward)
            
            dp.message.register(handle_russian, F.text)
            dp.callback_query.register(callback_handler)
            
            print("✅ Бот запущен")
            print("✅ Игры: монетка, кубик, слоты, мины, башня, алмазы, пирамида, краш, футбол, баскетбол, дартс, квак, кнб")
            print("✅ Банк работает")
            print("✅ Промокоды работают")
            print("✅ NFT система работает")
            print("✅ Система заданий работает")
            print("✅ Ивенты работают (money x2, crash x1.1)")
            print("✅ Админка работает (логи, топ общий, выдача статусов)")
            print("✅ Переводы с причиной работают")
            
            await dp.start_polling(bot)
            break
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            if attempt < max_retries - 1:
                print(f"⏳ Повтор через {retry_delay}с")
                await asyncio.sleep(retry_delay)
            else:
                print("\n❌ Не удалось подключиться")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Бот остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
