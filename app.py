import hashlib as hasher
from flask import Flask, request, jsonify, render_template, send_from_directory
from pymongo import MongoClient
import simplejson as json

from block import *
from transaction import Transaction

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

template_dir = os.path.abspath('./frontend')
app = Flask(__name__, template_folder=template_dir, static_url_path=template_dir)
client = MongoClient(os.getenv("MONGO_URL"),
                      username=os.getenv("MONGO_USERNAME"),
                      password=os.getenv("MONGO_PASSWORD"),
                      authSource=os.getenv("MONGO_AUTHSOURCE"),
                      authMechanism='SCRAM-SHA-1')

db = client.campcoin

def getBlockchain():
    blockchain = []
    blocks = db.blocks.find()
    for block in blocks:
        b = Block(block['index'], block['transactions'], block['nonce'], block['hash'])
        blockchain.append(b)
    return blockchain

transactions = [] #todo transactions in mongo

#db.blocks.insert_one(createGenesisBlock().__dict__)

def getBalance(public_key):
    balance = 0
    blockchain = getBlockchain()
    for block in blockchain:
        for transaction in json.loads(block.transactions):
            if (transaction["reciever"] == public_key):
                balance = balance + transaction["amount"]
            if (transaction["sender"] == public_key):
                balance = balance - transaction["amount"]

    return balance

def getPendingBalance(public_key):
    balance = 0
    for transaction in transactions:
        print(transaction)
        if (transaction.reciever == public_key):
                balance = balance + transaction.amount
        if (transaction.sender == public_key):
            balance = balance - transaction.amount

    return balance

def hasSufficentFunds(public_key, amount):
    balance = getBalance(public_key) + getPendingBalance(public_key)
    if (balance >= amount):
        return True
    return False

@app.route('/')
def frontend():
    return render_template("index.html")

@app.route('/<path:path>')
def send_js(path):
    return send_from_directory('frontend', path)

@app.route('/api/balance', methods=["POST"])
def balance():
    req = request.get_json()
    return str(getBalance(req["public_key"]))

@app.route('/api/chain')
def chain():
    blockchain = getBlockchain
    return jsonify(getBlockchain)

@app.route("/api/current")
def current():
    blockchain = getBlockchain()
    return jsonify(blockchain[-1])

@app.route("/api/mine", methods=['POST'])
def mine():
    global previousBlock
    global db

    req = request.get_json()
    block = Block(req["index"], req["transactions"], req["nonce"], previousBlock.hash, req["hash"])
    if not block.validate():
        return jsonify({"error": "Invalid hash"}), 400

    transactionStringArr = []
    for transaction in json.loads(block.transactions):
        transactionObject = Transaction(transaction["sender"], transaction["reciever"], transaction["amount"], transaction["signature"])
        if not transaction["sender"] == "MINER":
            if not transactionObject.verifyTransaction(transactionObject.sender):
                return jsonify({"error": "Bad Transaction in block"}), 400
            for trans in transactions:
                if trans.signature == transactionObject.signature:
                    print(trans.signature)
                    transactions.remove(trans)
                    break
            else:
                trans = None
            if trans == None:
                return jsonify({"error": "Bad Transaction in block"}), 400
        elif transaction["sender"] == "MINER":
            print("New block attempt by [" + transactionObject.reciever + "]")
            if transactionObject.amount != 1:
                return jsonify({"error": "Bad Transaction in block"}), 400

        transactionStringArr.append(str(transactionObject.amount) + " coin(s) " + transactionObject.sender + " --> " + transactionObject.reciever)
    
    insertBlock = Block(block.index, block.transactions, block.nonce, block.previousHash, block.hash)
    db.blocks.insert_one(insertBlock.__dict__)

    print("--New block successfully mined!--")
    print("Transactions:")
    for tStr in transactionStringArr:
        print(tStr)
    print("----------------")
    print("")
    return jsonify({"message": "New block successfully mined!"}), 200

@app.route("/api/transactions", methods=['POST'])
def createTransaction():
    req = request.get_json()
    transactionObject = Transaction(req["sender"], req["reciever"], req["amount"], req["signature"])
    if not transactionObject.verifyTransaction(transactionObject.sender):
        return jsonify({"error": "Bad Transaction"}), 400

    if not hasSufficentFunds(transactionObject.sender, transactionObject.amount):
        return jsonify({"error": "Insufficient Balance"}), 400

    transactions.append(transactionObject)
    return jsonify({"response": "Transaction Posted"})

@app.route("/api/transactions", methods=['GET'])
def getTransactions():
    return jsonify(transactions)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
