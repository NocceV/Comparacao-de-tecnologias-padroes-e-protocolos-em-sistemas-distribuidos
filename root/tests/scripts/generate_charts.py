import os
import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "figuras"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Cores harmoniosas para publicação científica
COLORS = {
    "websocket": "#2b5c8f",
    "grpc": "#2e7d32",
    "soap": "#e65100",
    "sse": "#00838f",
    "rest": "#1565c0",
    "webhook": "#6a1b9a",
    "graphql": "#c2185b"
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300
})

def generate_deterministic_latency_chart():
    protocols = ["WebSocket", "gRPC", "SOAP", "SSE", "REST", "Webhook", "GraphQL"]
    # Dados da execução determinística (100 reqs cada)
    user_lats = [0.58, 0.94, 6.16, 4.97, 5.56, 7.50, 5.80]
    msg_lats = [0.58, 1.35, 4.99, 7.28, 5.98, 7.36, 7.91]
    event_lats = [0.58, 1.37, 4.87, 3.86, 5.07, 6.01, 7.94]

    x = np.arange(len(protocols))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 5.5))
    rects1 = ax.bar(x - width, user_lats, width, label="user-service", color="#1f77b4")
    rects2 = ax.bar(x, msg_lats, width, label="message-service", color="#ff7f0e")
    rects3 = ax.bar(x + width, event_lats, width, label="event-service", color="#2ca02c")

    ax.set_ylabel("Latência Média (ms)")
    ax.set_title("Comparativo de Latência Média por Protocolo e Microsserviço (Regime Determinístico)")
    ax.set_xticks(x)
    ax.set_xticklabels(protocols)
    ax.legend(frameon=True)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    # Valores em cima das barras para clareza
    for rects in [rects1, rects2, rects3]:
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f"{height:.2f}",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "grafico_latencias_deterministicas.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Salvo: {out_path}")


def generate_throughput_chart():
    protocols = ["gRPC", "SSE", "SOAP", "REST", "WebSocket", "Webhook", "GraphQL"]
    throughputs = [794.55, 195.49, 186.11, 178.43, 176.41, 143.10, 139.43]
    colors = [COLORS[p.lower()] for p in protocols]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(protocols, throughputs, color=colors, edgecolor="black", linewidth=0.6)

    ax.set_ylabel("Vazão Média (requisições por segundo)")
    ax.set_title("Vazão Média (Throughput) por Tecnologia no Regime Determinístico")
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height:.1f} req/s",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontweight="bold", fontsize=9)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "grafico_throughput_comparativo.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Salvo: {out_path}")


def generate_stochastic_equality_chart():
    protocols = ["WebSocket", "REST", "SSE", "GraphQL", "SOAP", "Webhook", "gRPC"]
    req_counts = [30, 30, 30, 30, 30, 30, 30]
    latencies = [0.58, 4.02, 5.08, 5.70, 6.53, 6.56, 8.67]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1, 1.3]})

    # Painel 1: Igualdade estrita de requisições
    colors = [COLORS[p.lower()] for p in protocols]
    y = np.arange(len(protocols))
    ax1.barh(y, req_counts, color=colors, edgecolor="black", linewidth=0.5)
    ax1.set_yticks(y)
    ax1.set_yticklabels(protocols)
    ax1.set_xlabel("Número de Requisições")
    ax1.set_title("Distribuição Equânime (30 req / 14,3% cada)")
    ax1.set_xlim(0, 40)
    ax1.grid(axis="x", linestyle="--", alpha=0.5)
    for i, v in enumerate(req_counts):
        ax1.text(v + 1, i, f"{v} (14,3%)", va="center", fontweight="bold", fontsize=9)

    # Painel 2: Latência média no regime estocástico
    ax2.barh(y, latencies, color=colors, edgecolor="black", linewidth=0.5)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlabel("Latência Média (ms)")
    ax2.set_title("Latência Média sob Tráfego Estocástico")
    ax2.set_xlim(0, 12)
    ax2.grid(axis="x", linestyle="--", alpha=0.5)
    for i, v in enumerate(latencies):
        ax2.text(v + 0.3, i, f"{v:.2f} ms", va="center", fontweight="bold", fontsize=9)

    plt.suptitle("Regime Estocástico: Validação de Paridade Amostral e Desempenho", fontsize=13)
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "grafico_estocastico_igualdade.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Salvo: {out_path}")


def generate_grafana_telemetry_chart():
    # Gráfico simulando o painel consolidado do Grafana (Prometheus telemetry)
    fig, axs = plt.subplots(2, 2, figsize=(11, 7))

    # 1. Total Requisições HTTP (Prometheus http_requests_total)
    http_jobs = ["User REST", "Msg REST", "Event REST", "User SOAP", "Msg SOAP", "Event SOAP", "User Webhook", "Msg Webhook", "Event Webhook"]
    http_counts = [147, 147, 147, 130, 130, 130, 130, 130, 130]
    axs[0, 0].bar(http_jobs, http_counts, color="#1976d2")
    axs[0, 0].set_title("Prometheus: http_requests_total por Endpoint")
    axs[0, 0].set_ylabel("Total de Requisições")
    axs[0, 0].tick_params(axis="x", rotation=45)
    axs[0, 0].grid(axis="y", linestyle="--", alpha=0.5)

    # 2. Mensagens WebSocket vs Conexões
    ws_labels = ["User WS", "Msg WS", "Event WS"]
    ws_messages = [130, 130, 130]
    ws_conns = [130, 130, 130]
    x_ws = np.arange(len(ws_labels))
    axs[0, 1].bar(x_ws - 0.15, ws_messages, width=0.3, label="ws_messages_total", color="#388e3c")
    axs[0, 1].bar(x_ws + 0.15, ws_conns, width=0.3, label="ws_connections_total", color="#81c784")
    axs[0, 1].set_title("Grafana: Telemetria WebSocket (Conexões e Mensagens)")
    axs[0, 1].set_xticks(x_ws)
    axs[0, 1].set_xticklabels(ws_labels)
    axs[0, 1].legend()
    axs[0, 1].grid(axis="y", linestyle="--", alpha=0.5)

    # 3. Requisições gRPC
    grpc_labels = ["User gRPC", "Msg gRPC", "Event gRPC"]
    grpc_counts = [130, 130, 130]
    axs[1, 0].bar(grpc_labels, grpc_counts, color="#d32f2f")
    axs[1, 0].set_title("Prometheus: grpc_requests_total (Portas 50051/54/61)")
    axs[1, 0].set_ylabel("Chamadas RPC")
    axs[1, 0].grid(axis="y", linestyle="--", alpha=0.5)

    # 4. Eventos SSE
    sse_labels = ["User SSE", "Msg SSE", "Event SSE"]
    sse_events = [130, 130, 130]
    axs[1, 1].bar(sse_labels, sse_events, color="#0097a7")
    axs[1, 1].set_title("Grafana: sse_events_total por Serviço")
    axs[1, 1].set_ylabel("Eventos Transmitidos")
    axs[1, 1].grid(axis="y", linestyle="--", alpha=0.5)

    plt.suptitle("Painel de Telemetria e Observabilidade (Prometheus & Grafana)", fontsize=14, y=0.99)
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "grafico_telemetria_grafana_prometheus.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Salvo: {out_path}")


if __name__ == "__main__":
    generate_deterministic_latency_chart()
    generate_throughput_chart()
    generate_stochastic_equality_chart()
    generate_grafana_telemetry_chart()
    print("Todas as figuras foram geradas com sucesso!")
