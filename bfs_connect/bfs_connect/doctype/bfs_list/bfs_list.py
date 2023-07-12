# Copyright (c) 2023, itsdave and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import file_manager
import pandas as pd
import numpy as np
import os
from collections import namedtuple
from frappe.utils.file_manager import save_file


class BFSList(Document):

	@frappe.whitelist()
	def do_import(self):
		df = self.get_data_from_excel()
		erstelldatum = df["ERSTELLDATUM"][0]
		self.get_transaction_data("HCTRANS-03210")
		if self.check_erstelldatum(erstelldatum):
			print(erstelldatum)
			self.erstelldatum = erstelldatum
			sum_zahl_betrag = df["ZAHL_BETRAG"].sum()
			betrag = -round(sum_zahl_betrag,2)
			self.sum = sum_zahl_betrag
			print(sum_zahl_betrag)
			
			transaction = self.get_hibiscus_connect_transaction(betrag)
			if transaction: 
				self.hib_con_trans = transaction
				self.get_bfs_item(df,transaction)
				print(self.file)
				filename = os.path.basename(self.file)
				print(filename)
			else:
				frappe.throw("Zu diesem Avis wurde noch keine Transaktion durchgeführt")
		else:
			erstelldatum_str = erstelldatum.date()
			frappe.throw("Ein Avis mit dem Erstelldatum " + str(erstelldatum_str) + " wurde bereits verarbeitet.")
		if betrag and transaction:
			self.status = "complete"
		else:
			self.status = "incomplete"
		
		self.save()
		#frappe.msgprint("Import abgeschlossen.")
       
	def get_data_from_excel(self):  
		
		excel_file = frappe.utils.file_manager.get_file_path(self.file)
		
		df = pd.read_excel(excel_file)

		df = df.replace(np.nan, '', regex=True)
		print(df)
		return df
	
	def get_bfs_item(self, df, transaction=False):
		qty = len(df.index)
		output = "Beginn der Verarbeitung\nAnzahl der Vorgänge: " + str(qty) +"\n"
					 
		count = 0
		for index, row in df.iterrows():
			sup = row["AS_KUNDEN_KURZTEXT"]
			id = row["LIEFERANTEN_NR"]
			nr = row["BELEGNUMMER"]
			supplier = self.get_supplier(id, sup)
			if not supplier:
				output += "Die BFS Suplier ID " + str(id) +" wurde noch nicht dem Supplier " + str(sup) + " zugeordnet\n" 
				p_i = ""
			else:
				p_i = self.get_purchase_invoice(supplier, nr)
				if not p_i:
					output += "Es existiert keine Purchase Invoice mit der Supplier Invoice Number " + str(nr) +"\n"

			count += 1
			item_doc = frappe.get_doc({
				"doctype": "BFS List Item",
				"verband_nr": row["VERBAND_NR"],
				"mitglied_nr": row["MITGLIED_NR"],
				"lieferanten_nr": row["LIEFERANTEN_NR"],
				"as_kunden_kurztext": row["AS_KUNDEN_KURZTEXT"],
				"belegnummer": row["BELEGNUMMER"],
				"belegdatum": row["BELEGDATUM"],
				"erfassungsdatum": row["ERFASSUNGSDATUM"],
				"faelligkeitsdatum": row["FAELLIGKEITSDATUM"],
				"erstelldatum": row["ERSTELLDATUM"],
				"waehrungs_kz": row["WAEHRUNGS_KZ"],
				"rechnungsbetrag": row["RECHNUNGSBETRAG"],
				"sofortabzug_prozent": row["SOFORTABZUG_PROZENT"],
				"sofortabzug_betrag": row["SOFORTABZUG_BETRAG"],
				"sk_prozentsatz": row["SK_PROZENTSATZ"],
				"sk_betrag": row["SK_BETRAG"],
				"zahl_betrag": row["ZAHL_BETRAG"],
				"mwst_satz": row["MWST_SATZ"],
				"mwst_betrag": row["MWST_BETRAG"],
				"supplier": supplier,
				"hibiscus_connect_transaction": transaction,
				"purchase_invoice": p_i
			})

			print(item_doc)
			item_doc.save()
		output += "Es wurden " +str(count) +" BFS Items erzeugt"	
		self.output = output
		self.save()	

	def get_supplier(self,id,sup):
		supplier_list = frappe.get_all("Supplier",filters={"bfs_supplier_id":id})	
		if len(supplier_list) == 1:
			supplier = supplier_list[0]["name"]
	
		else:
			supplier = ""
		return supplier
	
	def get_hibiscus_connect_transaction(self,betrag):
		settings = frappe.get_single("BFS Settings")
		gegenkonto = settings.gegenkonto_name
		print(gegenkonto)
		print(betrag)
		filters={"betrag":betrag, "empfaenger_name":gegenkonto}
		trans_list = frappe.get_all("Hibiscus Connect Transaction",filters=filters)
		print(trans_list)
		if len(trans_list) == 1:
			trasaction = trans_list[0]["name"]

		else:
			trasaction = ""
		print("trasaction")
		print(trasaction)
		return trasaction
		
	def get_purchase_invoice(self, supplier, nr):
		filters = {"supplier":supplier,"bill_no": nr}
		p_invoice_list = frappe.get_all("Purchase Invoice", filters = filters)
		if len(p_invoice_list) == 1:
			p_inv = p_invoice_list[0]["name"]
		else:
			p_inv = ""
		return p_inv
	

	def check_erstelldatum (self,erstelldatum):

		avis_list = frappe.get_all("BFS List", filters={"erstelldatum":erstelldatum})
		if len(avis_list) == 0:
			return True
		else: 
			return False

	@frappe.whitelist()	
	def get_transaction_data(self, trans):
		settings = frappe.get_single("BFS Settings")
		row_25 = str(settings.blz) + "/" + str(settings.konto)
		row_28C = 1
		bank_trans = frappe.get_doc("Hibiscus Connect Transaction", trans) 
		date = bank_trans.datum

		filters = {"hibiscus_connect_transaction":trans}
		bfs_transaction_list = frappe.get_all("BFS List Item", filters=filters)
		trans_list =[x.name for x in bfs_transaction_list]
		print(bfs_transaction_list)
		transactions =[]
		for el in trans_list:
			trans_doc = frappe.get_doc("BFS List Item",el)
			supplier_name = frappe.get_doc("Supplier", trans_doc.supplier).supplier_name
			transaction ={
				"date": date,
				"ammount": -trans_doc.zahl_betrag,
				"description" : supplier_name + ", Rechnung: " + trans_doc.belegnummer,
				"name": supplier_name
			}
			transactions.append(transaction)
		print(transactions)
		return(transactions)
	
	# @frappe.whitelist()
	# def generate_mt940_file(self):
	# 	self.attach_file_to_doctype(self.get_mt940_file())
	


	@frappe.whitelist()
	def get_mt940_file(self):
		trans = self.hib_con_trans
		filename = self.hib_con_trans + '.sta'
		with Mt940Writer(filename) as writer:
			transactions = self.get_transaction_data(trans)
			for transaction in transactions:
				writer.write_transaction(transaction)
	
		print('Wrote {} transactions to file: {}.'.format(len(transactions), filename))
		with open(filename, 'r') as file:
			content = file.read()
		#print(content)
		self.attach_file_to_doctype(content,filename)
		
	
	def attach_file_to_doctype(self, content, file_name):
		
		file_doc = save_file(file_name, content, self.doctype, self.name, is_private=0)
		if file_doc:
		
			self.attached_file = file_doc.name
			self.save()

	
	

class Mt940Writer(Document):

	def __init__(self, filename):
		self.file = open(filename, 'w')
		
		self._write_header()

		self._date = None


	def __enter__(self):
		return self


	def __exit__(self, exc_type, exc_val, exc_tb):
		self.release()



	def release(self):
		
		if not self.file.closed:
			self.file.close()
		
	def write_transaction(self, transaction):
		
		self.file.writelines([
			Mt940.make_61(
				transaction["date"],
				transaction["ammount"]),
			Mt940.make_86(
				transaction["name"],
				transaction["description"])
		])

	def _write_header(self):
		settings = frappe.get_single("BFS Settings")
		row_25 = str(settings.blz) + "/" + str(settings.konto)
		blz = str(settings.blz)
		konto = str(settings.konto)
		print(blz, konto)
		
		row_28C = 1
		self.file.write(
			Mt940.make_header(""))
		self.file.writelines([
			Mt940.make_20("BFS-finance GmbH"),
			Mt940.make_25(blz,konto),
			Mt940.make_28(row_28C)
		])
	
	
		

CURRENCY = 'EUR'

# format identifier
TAG_940 = '940'

# header
FORMAT_HEADER = \
    '{bic}\n' + \
    TAG_940 + '\n' + \
    '{bic}\n'

# transaction ref
FORMAT_20 = ':20:{bank}\n'

# account id
FORMAT_25 = ':25:{blz}/{konto}\n'

# sequence no
FORMAT_28 = ':28:{seqno}\n'


# transaction
FORMAT_61 = ':61:{date}{date2}{amount}{magic}\n'

# transaction 2
FORMAT_86 = ':86:/NAME/{name}/REMI/{description}\n'

MAGIC = 'NTRFNONREF'


class Mt940:

    @staticmethod
    def make_header(bic):
        return FORMAT_HEADER.format(
            bic=bic)

    @staticmethod
    def make_20(bank):
        return FORMAT_20.format(
            bank=bank)

    @staticmethod
    def make_25(blz, konto):
        return FORMAT_25.format(
            blz=blz,
            konto=konto)

    @staticmethod
    def make_28(seqno):
        return FORMAT_28.format(
            seqno=Mt940.pad_5(seqno))


    @staticmethod
    def make_61(datetime, amount):
        return FORMAT_61.format(
            date=Mt940.date(datetime),
            date2=Mt940.date(datetime, with_year=False),
            amount=Mt940.amount(amount),
            magic=MAGIC)

    @staticmethod
    def make_86(name, description):
        return FORMAT_86.format(
            name=name,
            description=description)

    @staticmethod
    def pad_5(val):
        return str(val).zfill(5)

    @staticmethod
    def amount_sign(val):
        return 'CR' if val > 0 else 'DR'

    @staticmethod
    def amount_val(val):
        return '{0:.2f}'.format(abs(val)).replace('.', ',')

    @staticmethod
    def amount(val):
        return Mt940.amount_sign(val) + Mt940.amount_val(val)

    @staticmethod
    def date(val, with_year=True):
        if with_year:
            return val.strftime('%y%m%d')
        else:
            return val.strftime('%m%d')
