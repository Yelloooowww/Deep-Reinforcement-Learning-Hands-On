#!/usr/bin/env python3
import argparse
import logging

from libbots import subtitles, data, model

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable


DATA_FILE = "data/OpenSubtitles/en/Action/2005/365_100029_136606_sin_city.xml.gz"
HIDDEN_STATE_SIZE = 32
BATCH_SIZE = 16

log = logging.getLogger("train")


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)-15s %(levelname)s %(message)s", level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuda", action='store_true', default=False, help="Enable cuda")
    parser.add_argument("-n", "--name", required=True, help="Name of the run")
    args = parser.parse_args()

    dialogues = subtitles.read_file(DATA_FILE, dialog_seconds=5)
    log.info("Loaded %d dialogues with %d phrases", len(dialogues), sum(map(len, dialogues)))
    emb_dict, emb = data.read_embeddings()
    train_data = data.dialogues_to_train(dialogues, emb_dict)
    log.info("Training data converted, got %d samples", len(train_data))

    # initialize embedding lookup table
    embeddings = nn.Embedding(num_embeddings=emb.shape[0], embedding_dim=emb.shape[1])
    embeddings.weight.data.copy_(torch.from_numpy(emb))
    embeddings.weight.requires_grad = False
    if args.cuda:
        embeddings.cuda()

    net = model.PhraseModel(emb_size=emb.shape[1], dict_size=emb.shape[0], hid_size=HIDDEN_STATE_SIZE)
    if args.cuda:
        net.cuda()
    log.info("Model: %s", net)

    batch = train_data[:BATCH_SIZE]
    input_seq, out_seq_list, out_idx = model.pack_batch(batch, embeddings, cuda=args.cuda)
    enc = net.encode(input_seq)

    net_results = []
    net_targets = []
    for idx, out_seq in enumerate(out_seq_list):
        r = net.decode_teacher(enc[:, idx:idx+1], out_seq)
        net_results.append(r)
        net_targets.extend(out_idx[idx][1:])
    results_v = torch.cat(net_results)
    targets_v = Variable(torch.LongTensor(net_targets))
    if args.cuda:
        targets_v = targets_v.cuda()
    loss_v = F.cross_entropy(results_v, targets_v)
    loss_v.backward()

    pass