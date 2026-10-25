"""WavLM-large + AASIST speech deepfake detector (inference only)."""
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import WavLMModel


class _GraphAttentionLayer(nn.Module):
    def __init__(self, in_dim, out_dim, temperature):
        super().__init__()
        self.att_proj = nn.Linear(in_dim, out_dim)
        self.att_weight = nn.Parameter(torch.empty(out_dim, 1))
        self.proj_with_att = nn.Linear(in_dim, out_dim)
        self.proj_without_att = nn.Linear(in_dim, out_dim)
        self.bn = nn.BatchNorm1d(out_dim)
        self.temp = temperature

    def forward(self, x):
        N = x.size(1)
        x_i = x.unsqueeze(2).expand(-1, -1, N, -1)
        att = torch.matmul(torch.tanh(self.att_proj(x_i * x_i.transpose(1, 2))), self.att_weight) / self.temp
        att = F.softmax(att, dim=-2)
        out = self.proj_with_att(torch.matmul(att.squeeze(-1), x)) + self.proj_without_att(x)
        s = out.shape
        return F.selu(self.bn(out.reshape(-1, s[-1])).reshape(s))


class _HtrgGraphAttentionLayer(nn.Module):
    def __init__(self, in_dim, out_dim, temperature):
        super().__init__()
        self.proj_type1 = nn.Linear(in_dim, in_dim)
        self.proj_type2 = nn.Linear(in_dim, in_dim)
        self.att_proj = nn.Linear(in_dim, out_dim)
        self.att_projM = nn.Linear(in_dim, out_dim)
        self.att_weight11 = nn.Parameter(torch.empty(out_dim, 1))
        self.att_weight22 = nn.Parameter(torch.empty(out_dim, 1))
        self.att_weight12 = nn.Parameter(torch.empty(out_dim, 1))
        self.att_weightM = nn.Parameter(torch.empty(out_dim, 1))
        self.proj_with_att = nn.Linear(in_dim, out_dim)
        self.proj_without_att = nn.Linear(in_dim, out_dim)
        self.proj_with_attM = nn.Linear(in_dim, out_dim)
        self.proj_without_attM = nn.Linear(in_dim, out_dim)
        self.bn = nn.BatchNorm1d(out_dim)
        self.temp = temperature

    def forward(self, x1, x2, master):
        n1 = x1.size(1)
        x = torch.cat([self.proj_type1(x1), self.proj_type2(x2)], dim=1)
        N = x.size(1)
        x_i = x.unsqueeze(2).expand(-1, -1, N, -1)
        att_map = torch.tanh(self.att_proj(x_i * x_i.transpose(1, 2)))
        board = torch.zeros_like(att_map[:, :, :, 0]).unsqueeze(-1)
        board[:, :n1, :n1] = torch.matmul(att_map[:, :n1, :n1], self.att_weight11)
        board[:, n1:, n1:] = torch.matmul(att_map[:, n1:, n1:], self.att_weight22)
        board[:, :n1, n1:] = torch.matmul(att_map[:, :n1, n1:], self.att_weight12)
        board[:, n1:, :n1] = torch.matmul(att_map[:, n1:, :n1], self.att_weight12)
        board = F.softmax(board / self.temp, dim=-2)
        out = self.proj_with_att(torch.matmul(board.squeeze(-1), x)) + self.proj_without_att(x)
        s = out.shape
        out = F.selu(self.bn(out.reshape(-1, s[-1])).reshape(s))
        att_m = F.softmax(torch.matmul(torch.tanh(self.att_projM(x * master)), self.att_weightM) / self.temp, dim=-2)
        master = self.proj_with_attM(torch.matmul(att_m.squeeze(-1).unsqueeze(1), x)) + self.proj_without_attM(master)
        return out.narrow(1, 0, n1), out.narrow(1, n1, N - n1), master


class _GraphPool(nn.Module):
    def __init__(self, k, in_dim):
        super().__init__()
        self.k = k
        self.proj = nn.Linear(in_dim, 1)

    def forward(self, h):
        scores = torch.sigmoid(self.proj(h))
        n_keep = max(int(h.size(1) * self.k), 1)
        idx = torch.topk(scores, n_keep, dim=1)[1].expand(-1, -1, h.size(-1))
        return torch.gather(h * scores, 1, idx)


class AASISTPool(nn.Module):
    def __init__(self, feat_dim, num_layers, gat_dims=(128, 64),
                 pool_ratios=(0.5, 0.7, 0.5, 0.5), temps=(2.0, 2.0, 100.0, 100.0)):
        super().__init__()
        g = list(gat_dims)
        self.proj = nn.Linear(feat_dim, g[0])
        self.pos_S = nn.Parameter(torch.randn(1, num_layers, g[0]))
        self.master1 = nn.Parameter(torch.randn(1, 1, g[0]))
        self.master2 = nn.Parameter(torch.randn(1, 1, g[0]))
        self.GAT_S = _GraphAttentionLayer(g[0], g[0], temps[0])
        self.GAT_T = _GraphAttentionLayer(g[0], g[0], temps[1])
        self.HtrgGAT_11 = _HtrgGraphAttentionLayer(g[0], g[1], temps[2])
        self.HtrgGAT_12 = _HtrgGraphAttentionLayer(g[1], g[1], temps[3])
        self.HtrgGAT_21 = _HtrgGraphAttentionLayer(g[0], g[1], temps[2])
        self.HtrgGAT_22 = _HtrgGraphAttentionLayer(g[1], g[1], temps[3])
        self.pool_S = _GraphPool(pool_ratios[0], g[0])
        self.pool_T = _GraphPool(pool_ratios[1], g[0])
        self.pool_hS1 = _GraphPool(pool_ratios[2], g[1])
        self.pool_hT1 = _GraphPool(pool_ratios[2], g[1])
        self.pool_hS2 = _GraphPool(pool_ratios[2], g[1])
        self.pool_hT2 = _GraphPool(pool_ratios[2], g[1])
        self.output_dim = 5 * g[1]

    def forward(self, hidden_states):
        projected = self.proj(torch.stack(hidden_states, dim=1))
        e_S = torch.max(torch.abs(projected), dim=2)[0] + self.pos_S
        e_T = torch.max(torch.abs(projected), dim=1)[0]
        out_S = self.pool_S(self.GAT_S(e_S))
        out_T = self.pool_T(self.GAT_T(e_T))
        out_T1, out_S1, m1 = self.HtrgGAT_11(out_T, out_S, self.master1)
        out_S1, out_T1 = self.pool_hS1(out_S1), self.pool_hT1(out_T1)
        a_T, a_S, a_m = self.HtrgGAT_12(out_T1, out_S1, m1)
        out_T1, out_S1, m1 = out_T1 + a_T, out_S1 + a_S, m1 + a_m
        out_T2, out_S2, m2 = self.HtrgGAT_21(out_T, out_S, self.master2)
        out_S2, out_T2 = self.pool_hS2(out_S2), self.pool_hT2(out_T2)
        a_T, a_S, a_m = self.HtrgGAT_22(out_T2, out_S2, m2)
        out_T2, out_S2, m2 = out_T2 + a_T, out_S2 + a_S, m2 + a_m
        out_T, out_S, master = torch.max(out_T1, out_T2), torch.max(out_S1, out_S2), torch.max(m1, m2)
        return torch.cat([torch.max(torch.abs(out_T), 1)[0], out_T.mean(1),
                          torch.max(torch.abs(out_S), 1)[0], out_S.mean(1), master.squeeze(1)], dim=1)


class MLPBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, dim * 2), nn.GELU(), nn.Dropout(0.1),
                                 nn.Linear(dim * 2, dim), nn.GELU(), nn.Dropout(0.1))

    def forward(self, x):
        return self.net(x)


class Classifier(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_layers, num_labels=1):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, hidden_dim) if input_dim != hidden_dim else nn.Identity()
        self.mlp_blocks = nn.ModuleList([MLPBlock(hidden_dim) for _ in range(num_layers)])
        self.layer_norms = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(num_layers)])
        self.output_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.GELU(),
                                         nn.Dropout(0.1), nn.Linear(hidden_dim, num_labels))

    def forward(self, x):
        x = self.input_proj(x)
        for mlp, ln in zip(self.mlp_blocks, self.layer_norms):
            x = x + mlp(ln(x))
        return self.output_head(x)


class DeepfakeDetector(nn.Module):
    def __init__(self, hidden_dim=320, classifier_layers=3, aasist_gat_dims=(128, 64)):
        super().__init__()
        self.wavlm = WavLMModel.from_pretrained("microsoft/wavlm-large")
        self.pool = AASISTPool(self.wavlm.config.hidden_size, self.wavlm.config.num_hidden_layers, aasist_gat_dims)
        self.classifier = Classifier(self.pool.output_dim, hidden_dim, classifier_layers)

    @torch.no_grad()
    def forward(self, waveform):                       # (B, T) 16 kHz -> logit (B,); sigmoid(logit)=P(real)
        hs = list(self.wavlm(waveform, output_hidden_states=True).hidden_states[1:])
        return self.classifier(self.pool(hs)).squeeze(-1)
