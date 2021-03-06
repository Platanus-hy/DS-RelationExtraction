import os
import sys
import numpy as np
import cPickle as pickle
from collections import Counter
from collections import OrderedDict
from stanza.text.dataset import Dataset
from multiprocessing import Process, Pipe
import tree
from tqdm import tqdm
import math
import time
import json

try:
	dataset = sys.argv[1]
except:
	dataset = 'tacred'


SHORTEST_PATH_MODE = 'ancestor'  # can be 'root' or 'ancestor'

PAD_TOKEN = '<PAD>'
UNK_TOKEN = '<UNK>'
PAD_ID = 0
UNK_ID = 1

# use the count of words to build vocab, instead of using a fixed-size vocab
MIN_WORD_COUNT = 2
USE_COUNT = True

WORD_FIELD = 'token'
LABEL_FIELD = 'label'
POS_FIELD = 'stanford_pos'
NER_FIELD = 'stanford_ner'
DEPREL_FIELD = 'stanford_deprel'
DEPHEAD_FIELD = 'stanford_head'

ROOT_FIELD = 'root'  # the new field used to identify the root/ancestor in the shortest path

DEPHEAD_ROOT_ID = 0

EMPTY_ID = '-'

DATA_ROOT = "../data/%s/" % dataset.upper()

TRAIN_DEP_FILE = DATA_ROOT + 'train.json'
TEST_DEP_FILE = DATA_ROOT + 'test.json'

TRAIN_LABEL_FILE = DATA_ROOT + 'train_label.json'
TEST_LABEL_FILE = DATA_ROOT + 'test_label.json'

# hard-coded mappings from fields to ids

# TACRED
if dataset == 'tacred':
	SUBJ_NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'ORGANIZATION': 2, 'PERSON': 3}
	OBJ_NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'PERSON': 2, 'ORGANIZATION': 3, 'DATE': 4, 'NUMBER': 5, 'TITLE': 6,
					'COUNTRY': 7, 'LOCATION': 8, 'CITY': 9, 'MISC': 10, 'STATE_OR_PROVINCE': 11, 'DURATION': 12,
					'NATIONALITY': 13, 'CAUSE_OF_DEATH': 14, 'CRIMINAL_CHARGE': 15, 'RELIGION': 16, 'URL': 17,
					'IDEOLOGY': 18}
	NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'O': 2, 'PERSON': 3, 'ORGANIZATION': 4, 'LOCATION': 5, 'DATE': 6, 'NUMBER': 7,
				'MISC': 8, 'DURATION': 9, 'MONEY': 10, 'PERCENT': 11, 'ORDINAL': 12, 'TIME': 13, 'SET': 14}
	POS_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'NNP': 2, 'NN': 3, 'IN': 4, 'DT': 5, ',': 6, 'JJ': 7, 'NNS': 8, 'VBD': 9,
				'CD': 10, 'CC': 11, '.': 12, 'RB': 13, 'VBN': 14, 'PRP': 15, 'TO': 16, 'VB': 17, 'VBG': 18, 'VBZ': 19,
				'PRP$': 20, ':': 21, 'POS': 22, '\'\'': 23, '``': 24, '-RRB-': 25, '-LRB-': 26, 'VBP': 27, 'MD': 28,
				'NNPS': 29, 'WP': 30, 'WDT': 31, 'WRB': 32, 'RP': 33, 'JJR': 34, 'JJS': 35, '$': 36, 'FW': 37, 'RBR': 38,
				'SYM': 39, 'EX': 40, 'RBS': 41, 'WP$': 42, 'PDT': 43, 'LS': 44, 'UH': 45, '#': 46}
	DEPREL_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'punct': 2, 'compound': 3, 'case': 4, 'nmod': 5, 'det': 6, 'nsubj': 7,
					'amod': 8, 'conj': 9, 'dobj': 10, 'ROOT': 11, 'cc': 12, 'nmod:poss': 13, 'mark': 14, 'advmod': 15,
					'appos': 16, 'nummod': 17, 'dep': 18, 'ccomp': 19, 'aux': 20, 'advcl': 21, 'acl:relcl': 22, 'xcomp': 23,
					'cop': 24, 'acl': 25, 'auxpass': 26, 'nsubjpass': 27, 'nmod:tmod': 28, 'neg': 29, 'compound:prt': 30,
					'mwe': 31, 'parataxis': 32, 'root': 33, 'nmod:npmod': 34, 'expl': 35, 'csubj': 36, 'cc:preconj': 37,
					'iobj': 38, 'det:predet': 39, 'discourse': 40, 'csubjpass': 41}

	LABEL_TO_ID = {'no_relation': 0, 'per:title': 1, 'org:top_members/employees': 2, 'per:employee_of': 3,
				'org:alternate_names': 4, 'org:country_of_headquarters': 5, 'per:countries_of_residence': 6,
				'org:city_of_headquarters': 7, 'per:cities_of_residence': 8, 'per:age': 9,
				'per:stateorprovinces_of_residence': 10, 'per:origin': 11, 'org:subsidiaries': 12, 'org:parents': 13,
				'per:spouse': 14, 'org:stateorprovince_of_headquarters': 15, 'per:children': 16, 'per:other_family': 17,
				'per:alternate_names': 18, 'org:members': 19, 'per:siblings': 20, 'per:schools_attended': 21,
				'per:parents': 22, 'per:date_of_death': 23, 'org:member_of': 24, 'org:founded_by': 25, 'org:website': 26,
				'per:cause_of_death': 27, 'org:political/religious_affiliation': 28, 'org:founded': 29,
				'per:city_of_death': 30, 'org:shareholders': 31, 'org:number_of_employees/members': 32,
				'per:date_of_birth': 33, 'per:city_of_birth': 34, 'per:charges': 35, 'per:stateorprovince_of_death': 36,
				'per:religion': 37, 'per:stateorprovince_of_birth': 38, 'per:country_of_birth': 39, 'org:dissolved': 40,
				'per:country_of_death': 41}

# KBP
elif dataset == 'kbp':
	SUBJ_NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'ORGANIZATION': 2, 'PERSON': 3, 'LOCATION': 4, 'MISC': 5}

	OBJ_NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'ORGANIZATION': 2, 'PERSON': 3, 'LOCATION': 4, 'MISC': 5}

	NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'O': 2, 'PERSON': 3, 'ORGANIZATION': 4, 'LOCATION': 5, 'DATE': 6, 'NUMBER': 7,
				'MISC': 8, 'DURATION': 9, 'MONEY': 10, 'PERCENT': 11, 'ORDINAL': 12, 'TIME': 13, 'SET': 14}

	POS_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'NNP': 2, 'NN': 3, 'IN': 4, 'DT': 5, ',': 6, 'JJ': 7, 'NNS': 8, 'VBD': 9,
				'CD': 10, 'CC': 11, '.': 12, 'RB': 13, 'VBN': 14, 'PRP': 15, 'TO': 16, 'VB': 17, 'VBG': 18, 'VBZ': 19,
				'PRP$': 20, ':': 21, 'POS': 22, '\'\'': 23, '``': 24, '-RRB-': 25, '-LRB-': 26, 'VBP': 27, 'MD': 28,
				'NNPS': 29, 'WP': 30, 'WDT': 31, 'WRB': 32, 'RP': 33, 'JJR': 34, 'JJS': 35, '$': 36, 'FW': 37, 'RBR': 38,
				'SYM': 39, 'EX': 40, 'RBS': 41, 'WP$': 42, 'PDT': 43, 'LS': 44, 'UH': 45, '#': 46}

	DEPREL_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'punct': 2, 'compound': 3, 'case': 4, 'nmod': 5, 'det': 6, 'nsubj': 7,
					'amod': 8, 'conj': 9, 'dobj': 10, 'ROOT': 11, 'cc': 12, 'nmod:poss': 13, 'mark': 14, 'advmod': 15,
					'appos': 16, 'nummod': 17, 'dep': 18, 'ccomp': 19, 'aux': 20, 'advcl': 21, 'acl:relcl': 22, 'xcomp': 23,
					'cop': 24, 'acl': 25, 'auxpass': 26, 'nsubjpass': 27, 'nmod:tmod': 28, 'neg': 29, 'compound:prt': 30,
					'mwe': 31, 'parataxis': 32, 'root': 33, 'nmod:npmod': 34, 'expl': 35, 'csubj': 36, 'cc:preconj': 37,
					'iobj': 38, 'det:predet': 39, 'discourse': 40, 'csubjpass': 41}

	LABEL_TO_ID = {'no_relation': 0, 'per:country_of_death': 1, 'per:country_of_birth': 2, 'per:parents': 3,
				'per:children': 4, 'per:religion': 5, 'per:countries_of_residence': 6}

# NYT
elif dataset == 'nyt':
	SUBJ_NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'ORGANIZATION': 2, 'PERSON': 3, 'LOCATION': 4, 'MISC': 5}

	OBJ_NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'ORGANIZATION': 2, 'PERSON': 3, 'LOCATION': 4, 'MISC': 5}

	NER_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'O': 2, 'PERSON': 3, 'ORGANIZATION': 4, 'LOCATION': 5, 'DATE': 6, 'NUMBER': 7,
				'MISC': 8, 'DURATION': 9, 'MONEY': 10, 'PERCENT': 11, 'ORDINAL': 12, 'TIME': 13, 'SET': 14}

	POS_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'NNP': 2, 'NN': 3, 'IN': 4, 'DT': 5, ',': 6, 'JJ': 7, 'NNS': 8, 'VBD': 9,
				'CD': 10, 'CC': 11, '.': 12, 'RB': 13, 'VBN': 14, 'PRP': 15, 'TO': 16, 'VB': 17, 'VBG': 18, 'VBZ': 19,
				'PRP$': 20, ':': 21, 'POS': 22, '\'\'': 23, '``': 24, '-RRB-': 25, '-LRB-': 26, 'VBP': 27, 'MD': 28,
				'NNPS': 29, 'WP': 30, 'WDT': 31, 'WRB': 32, 'RP': 33, 'JJR': 34, 'JJS': 35, '$': 36, 'FW': 37, 'RBR': 38,
				'SYM': 39, 'EX': 40, 'RBS': 41, 'WP$': 42, 'PDT': 43, 'LS': 44, 'UH': 45, '#': 46}

	DEPREL_TO_ID = {PAD_TOKEN: 0, UNK_TOKEN: 1, 'punct': 2, 'compound': 3, 'case': 4, 'nmod': 5, 'det': 6, 'nsubj': 7,
					'amod': 8, 'conj': 9, 'dobj': 10, 'ROOT': 11, 'cc': 12, 'nmod:poss': 13, 'mark': 14, 'advmod': 15,
					'appos': 16, 'nummod': 17, 'dep': 18, 'ccomp': 19, 'aux': 20, 'advcl': 21, 'acl:relcl': 22, 'xcomp': 23,
					'cop': 24, 'acl': 25, 'auxpass': 26, 'nsubjpass': 27, 'nmod:tmod': 28, 'neg': 29, 'compound:prt': 30,
					'mwe': 31, 'parataxis': 32, 'root': 33, 'nmod:npmod': 34, 'expl': 35, 'csubj': 36, 'cc:preconj': 37,
					'iobj': 38, 'det:predet': 39, 'discourse': 40, 'csubjpass': 41}

	LABEL_TO_ID = {
				"/business/person/company": 0,
				"/people/person/nationality": 1,
				"/people/deceased_person/place_of_death": 2,
				"/location/country/capital": 3,
				"/location/location/contains": 4,
				"/people/person/place_lived": 5,
				"/people/person/children": 6,
				"/location/country/administrative_divisions": 7,
				"/location/administrative_division/country": 8,
				"/people/person/place_of_birth": 9,
				"/location/neighborhood/neighborhood_of": 10,
				'no_relation': 11,
				"/business/company/major_shareholders": 12,
				"/business/company_shareholder/major_shareholder_of": 13,
				"/business/company/place_founded": 14,
				"/business/company/founders": 15,
				"/sports/sports_team/location": 16,
				"/sports/sports_team_location/teams": 17,
				"/business/company/advisors": 18,
				"/people/person/ethnicity": 19,
				"/people/ethnicity/people": 20,
				"/people/ethnicity/geographic_distribution": 21,
				"/people/person/religion": 22,
				"/people/person/profession": 23
				}

MAX_SEQ_LEN = 100
np.random.seed(1234)


def load_datasets(fname, labelfname, maxlen=MAX_SEQ_LEN, lowercase=True):
	with open(fname, 'r') as f:
		instances = json.load(f)
	with open(labelfname, 'r') as f:
		labels = json.load(f)
	# d = Dataset.load_conll(fn)
	print "Filtering long seq"
	dataset = OrderedDict()
	dataset[WORD_FIELD] = []
	dataset[POS_FIELD] = []
	dataset[DEPREL_FIELD] = []
	dataset[LABEL_FIELD] = []
	dataset[ROOT_FIELD] = []
	for idx, instance in enumerate(instances):
		if len(instance[0]) < maxlen:   # filter length
			words = instance[0]
			pos = [tok.upper() for tok in instance[1]]  # POS to upper case
			deprel = instance[2]
			dirs = instance[3]
			label = labels[idx]
			length = len(dirs)
			roots = ['_'] * length
			# find root in path
			for j in range(length - 1, -1, -1):
				if j != '2':
					roots[j] = 'ROOT'
					break
			dataset[WORD_FIELD].append(words)
			dataset[POS_FIELD].append(pos)
			dataset[DEPREL_FIELD].append(deprel)
			dataset[ROOT_FIELD].append(roots)
			dataset[LABEL_FIELD].append(label)
	dataset = Dataset(dataset)
	print "\t%d examples in %s" % (len(dataset), fname)
	return dataset


def build_vocab(datasets, use_count):
	c = Counter()
	for d in datasets:
		for row in d:
			c.update(row['token'])
	print "%d tokens found in dataset." % len(c)
	if use_count:
		print "Use min word count threshold to create vocab."
		all_words = [k for k, v in c.items() if v >= MIN_WORD_COUNT]
		word_id_pairs = [(x, i + 2) for i, x in enumerate(all_words)]
	else:
		print "Use fixed vocab size of " + str(VOCAB_SIZE)
		word_id_pairs = [(x[0], i + 2) for i, x in enumerate(c.most_common(VOCAB_SIZE - 2))]
	word_id_pairs += [(UNK_TOKEN, UNK_ID), (PAD_TOKEN, PAD_ID)]
	word2id = dict(word_id_pairs)
	return word2id


def build_vocab_for_field(datasets, fieldname):
	c = Counter()
	for d in datasets:
		for row in d:
			if isinstance(row[fieldname], str):
				c.update([row[fieldname]])
			else:
				c.update(row[fieldname])
	if fieldname == 'label':
		field2id = dict([(x[0], i) for i, x in enumerate(c.most_common())])
	else:
		token_id_pairs = [(x[0], i + 2) for i, x in enumerate(c.most_common())]
		token_id_pairs += [(UNK_TOKEN, UNK_ID), (PAD_TOKEN, PAD_ID)]
		field2id = dict(token_id_pairs)
	print "%d unique %s field found in datasets." % (len(field2id), fieldname)
	return field2id

def convert_words_to_ids(datasets, word2id):
	new_datasets = []
	for d in datasets:
		for i, row in enumerate(d):
			tokens = row['token']
			tokens_by_ids = [word2id[x] if x in word2id else UNK_ID for x in tokens]
			d.fields['token'][i] = tokens_by_ids
		new_datasets.append(d)
	return new_datasets


def convert_fields_to_ids(datasets, field2map):
	new_datasets = []
	for d in datasets:
		for f, m in field2map.iteritems():  # f is fieldname, m is the field2id map
			for i, l in enumerate(d.fields[f]):
				if isinstance(l, list):  # the field could be list, in case like NER
					for j, w in enumerate(l):
						d.fields[f][i][j] = m[w] if w in m else UNK_ID
				else:  # or can be just a label
					if l in m:
						d.fields[f][i] = m[l]
					else:
						print 'Error: label %s not exist' % l
		new_datasets.append(d)
	return new_datasets


def preprocess():
	print "Loading dependency path data from files..."
	d_train = load_datasets(TRAIN_DEP_FILE, TRAIN_LABEL_FILE, MAX_SEQ_LEN)
	d_test = load_datasets(TEST_DEP_FILE, TEST_LABEL_FILE, MAX_SEQ_LEN)
	print "Build vocab from training set..."
	word2id = build_vocab([d_train], USE_COUNT)
	VOCAB_SIZE = len(word2id)
	vocab_file = DATA_ROOT + "dependency/vocab"
	dump_to_file(vocab_file, word2id)
	print "Vocab with %d words saved to file %s" % (len(word2id), vocab_file)

	print "Collecting labels, pos tags, ner tags, and deprel tags..."
	# label2id = build_vocab_for_field([d_train], LABEL_FIELD)
	# dump_to_file(LABEL2ID_FILE, label2id)

	print "Converting data to ids..."
	d_train, d_test = convert_words_to_ids([d_train, d_test], word2id)
	d_train, d_test = convert_fields_to_ids([d_train, d_test],
											{POS_FIELD: POS_TO_ID, DEPREL_FIELD: DEPREL_TO_ID})

	# generate file names
	TRAIN_ID_FILE = DATA_ROOT + 'dependency/train.id'
	TEST_ID_FILE = DATA_ROOT + 'dependency/test.id'
	dump_to_file(TRAIN_ID_FILE, d_train)
	dump_to_file(TEST_ID_FILE, d_test)
	print "Datasets saved to files."
	max_length = 0
	for d in [d_train, d_test]:
		for row in d:
			l = len(row['token'])
			if l > max_length:
				max_length = l
	print "Datasets maximum sequence length is %d." % max_length
	print "Generating CV dataset on test set"
	total_len = len(d_test)
	dev_len = int(total_len*0.1)
	dev_list = []
	test_list = []
	for i in range(100):
		d_test.shuffle()
		dev_list.append(Dataset(d_test[:dev_len]))
		test_list.append(Dataset(d_test[dev_len:]))
	idx = 0
	for dev, test in zip(dev_list, test_list):
		test_cv_file = DATA_ROOT + 'dependency/cv/test.id.%d' % idx
		dev_cv_file = DATA_ROOT + 'dependency/cv/dev.id.%d' % idx
		dump_to_file(test_cv_file, test)
		dump_to_file(dev_cv_file, dev)
		idx += 1


def dump_to_file(filename, obj):
	with open(filename, 'wb') as outfile:
		pickle.dump(obj, file=outfile)
	return


def load_from_dump(filename):
	with open(filename, 'rb') as infile:
		obj = pickle.load(infile)
	return obj


class DataLoader():
	def __init__(self, dump_name, batch_size, pad_len, shuffle=True, subsample=1, unk_prob=0):
		self.dataset = load_from_dump(dump_name)
		if shuffle:
			self.dataset = self.dataset.shuffle()
		if subsample < 1:
			n = int(subsample * len(self.dataset))
			self.dataset = Dataset(self.dataset[:n])
		self.batch_size = batch_size
		self.num_examples = len(self.dataset)
		self.num_batches = self.num_examples // self.batch_size
		self.num_residual = self.num_examples - self.batch_size * self.num_batches
		self.pad_len = pad_len
		self._unk_prob = unk_prob
		self._pointer = 0

	def next_batch(self):
		"""
		Generate the most simple batch. x_batch is sentences, y_batch is labels, and x_lens is the unpadded length of sentences in x_batch.
		"""
		x_batch = {WORD_FIELD: [], POS_FIELD: [], DEPREL_FIELD: [], ROOT_FIELD: []}
		x_lens = []
		for field in x_batch.keys():
			for tokens in self.dataset.fields[field][self._pointer:self._pointer + self.batch_size]:
				# apply padding to the left
				assert self.pad_len >= len(tokens), "Padding length is shorter than original sentence length."
				if field == WORD_FIELD:
					if self._unk_prob > 0:
						tokens = self.corrupt_sentence(tokens)
					x_lens.append(len(tokens))
				tokens = tokens + [PAD_ID] * (self.pad_len - len(tokens))
				x_batch[field].append(tokens)
		y_batch = self.dataset.fields[LABEL_FIELD][self._pointer:self._pointer + self.batch_size]
		self._pointer += self.batch_size
		return x_batch, y_batch, x_lens

	def get_residual(self):
		x_batch = {WORD_FIELD: [], POS_FIELD: [], DEPREL_FIELD: [], ROOT_FIELD: []}
		x_lens = []
		for field in x_batch.keys():
			for tokens in self.dataset.fields[field][self._pointer:]:
				if field == WORD_FIELD:
					if self._unk_prob > 0:
						tokens = self.corrupt_sentence(tokens)
					x_lens.append(len(tokens))
				tokens = tokens + [PAD_ID] * (self.pad_len - len(tokens))
				x_batch[field].append(tokens)
		y_batch = self.dataset.fields[LABEL_FIELD][self._pointer:]
		return x_batch, y_batch, x_lens

	def reset_pointer(self):
		self._pointer = 0

	def corrupt_sentence(self, tokens):
		new_tokens = []
		for x in tokens:
			if x != UNK_ID and np.random.random() < self._unk_prob:
				new_tokens.append(UNK_ID)
			else:
				new_tokens.append(x)
		return new_tokens

	def write_keys(self, key_file, id2label=None, include_residual=False):
		if id2label is None:
			id2label = lambda x: x  # map to itself
		if include_residual:
			end_index = self.num_examples
		else:
			end_index = self.num_batches * self.batch_size
		labels = [id2label[l] for l in self.dataset.fields[LABEL_FIELD][:end_index]]
		# write to file
		with open(key_file, 'w') as outfile:
			for l in labels:
				outfile.write(str(l) + '\n')
		return


def main():
	preprocess()


if __name__ == '__main__':
	main()
