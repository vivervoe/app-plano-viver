import flet as ft
import requests
import math
import time
import webbrowser
import json
import os
import urllib.parse  # Usando urllib para codificação de URL

# Imports para geração do PDF da Carteirinha
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# =========================================================================
# ⚙️ CONFIGURAÇÕES DA API DO ASAAS (USANDO VARIÁVEIS DE AMBIENTE)
# =========================================================================
ASAAS_API_URL = os.environ.get("ASAAS_API_URL", "https://sandbox.asaas.com/api/v3")
ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY", "").strip()

HEADERS = {
    "accept": "application/json",
    "access_token": ASAAS_API_KEY
}

ARQUIVO_SESSAO = "sessao_viver.json"
PASTA_PDFS = "pdfs_gerados"

# Garante que a pasta para servir arquivos estáticos/PDFs exista
if not os.path.exists(PASTA_PDFS):
    os.makedirs(PASTA_PDFS)


def obtener_boletos_asaas(cpf_cliente, nome_cliente="João da Silva"):
    if not ASAAS_API_KEY:
        print("[AVISO] ASAAS_API_KEY não configurada em variáveis de ambiente.", flush=True)
        return []

    try:
        cpf_limpo = "".join([c for c in str(cpf_cliente) if c.isdigit()])
        
        print(f"\n[DIAGNÓSTICO] Consultando API Asaas...", flush=True)
        resposta = requests.get(f"{ASAAS_API_URL}/customers", headers=HEADERS, params={"limit": 100}, timeout=10)
        
        if resposta.status_code != 200:
            print(f"[ERRO API] Status Code: {resposta.status_code} - Resposta: {resposta.text}", flush=True)
            return []
            
        clientes = resposta.json().get("data", [])
        
        cliente_encontrado = None
        for cli in clientes:
            cpf_cli = "".join([c for c in str(cli.get("cpfCnpj", "")) if c.isdigit()])
            nome_cli = str(cli.get("name", "")).strip().lower()
            
            if (cpf_limpo and cpf_limpo in cpf_cli) or ("joao" in nome_cli or "silva" in nome_cli):
                cliente_encontrado = cli
                break

        if not cliente_encontrado:
            return []
            
        cliente_id = cliente_encontrado["id"]
        
        resp_cobrancas = requests.get(
            f"{ASAAS_API_URL}/payments", 
            headers=HEADERS, 
            params={"customer": cliente_id, "limit": 50},
            timeout=10
        )
        
        if resp_cobrancas.status_code == 200:
            cobrancas = resp_cobrancas.json().get("data", [])
            return [c for c in cobrancas if c.get("status") not in ["DELETED", "CANCELLED"]]
            
    except Exception as e:
        print(f"[ERRO EXCEÇÃO]: {e}", flush=True)
        
    return []


def obtener_pix_asaas(payment_id):
    if not ASAAS_API_KEY:
        return None
    try:
        resposta = requests.get(f"{ASAAS_API_URL}/payments/{payment_id}/pixQrCode", headers=HEADERS, timeout=8)
        if resposta.status_code == 200:
            return resposta.json()
    except Exception as e:
        print(f"[ERRO PIX]: {e}", flush=True)
    return None


# =========================================================================
# 📱 CÓDIGO DA APLICAÇÃO FLET
# =========================================================================

async def main(page: ft.Page):
    CPF_TESTE = "077.125.370-20" 
    SENHA_TESTE = "1234"
    
    COR_PRINCIPAL = "#005F56"
    COR_GRADIENT_FIM = "#008B7D"
    COR_BORDA_GOLD = "#FBC02D"    
    
    perfil_atual = {"chave": "titular", "nome": "JOÃO DA SILVA"}

    page.title = "Plano Viver - Área do Cliente"
    page.theme_mode = ft.ThemeMode.LIGHT 
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.bgcolor = "#F1F5F9"

    # --- ARMAZENAMENTO LOCAL / PWA (SUPORTE OFFLINE) ---
    dados_padrao_carteirinhas = {
        "titular": {"nome": "JOÃO DA SILVA", "numero": "001.2345.678900-12", "plano": "VIVER GLOBAL (PLANO PRATA)", "validade": "12/2028", "avatar": "👤", "status": "ATIVO", "vencimento": "10/08/2026"},
        "dep1": {"nome": "PEDRO DA SILVA (DEP)", "numero": "001.2345.678900-13", "plano": "VIVER GLOBAL (PLANO PRATA)", "validade": "12/2028", "avatar": "👦", "status": "ATIVO", "vencimento": "10/08/2026"},
        "dep2": {"nome": "MARIA DA SILVA (DEP)", "numero": "001.2345.678900-14", "plano": "VIVER GLOBAL (PLANO PRATA)", "validade": "12/2028", "avatar": "👧", "status": "ATIVO", "vencimento": "10/08/2026"}
    }

    # Restaura dados salvos localmente se existirem (Assíncrono)
    try:
        has_key = await page.shared_preferences.contains_key("dados_carteirinhas")
        if has_key:
            dados_carteirinhas = await page.shared_preferences.get("dados_carteirinhas")
            if not isinstance(dados_carteirinhas, dict):
                dados_carteirinhas = dados_padrao_carteirinhas
        else:
            dados_carteirinhas = dados_padrao_carteirinhas
            await page.shared_preferences.set("dados_carteirinhas", dados_carteirinhas)
    except Exception:
        dados_carteirinhas = dados_padrao_carteirinhas

    async def salvar_carteirinhas_localment():
        await page.shared_preferences.set("dados_carteirinhas", dados_carteirinhas)

    dados_historico_consultas = [
        {"data": "10/05/2026", "especialidade": "Cardiologia", "medico": "Dr. Fernando Rosa", "local": "Prontocor Clínica", "valor": 230.00, "particular": 450.00, "status": "Realizada"},
        {"data": "22/03/2026", "especialidade": "Oftalmologia", "medico": "Dra. Camila Ribeiro", "local": "Hospital Sadalla", "valor": 240.00, "particular": 400.00, "status": "Realizada"},
        {"data": "15/01/2026", "especialidade": "Clínico Geral", "medico": "Dr. Henrique Silva", "local": "Clínica Voe Saúde", "valor": 180.00, "particular": 350.00, "status": "Realizada"}
    ]

    async def alternar_tema(e):
        page.theme_mode = ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
        page.bgcolor = "#111827" if page.theme_mode == ft.ThemeMode.DARK else "#F1F5F9"
        await page.update_async() if hasattr(page, 'update_async') else page.update()

    async def abrir_whatsapp(e, tipo_contato="suporte"):
        numero_whatsapp = "554791362438" 
        primeiro_nome = perfil_atual["nome"].split()[0].title()
        
        if tipo_contato == "assistente":
            mensagem = f"Olá, me chamo {primeiro_nome}, vim pelo app do viver e gostaria de agendamento"
        else:
            mensagem = f"Olá! Sou o {primeiro_nome}. Estou usando o aplicativo do Plano Viver e preciso de ajuda com o suporte."
            
        url = f"https://api.whatsapp.com/send?phone={numero_whatsapp}&text={urllib.parse.quote(mensagem)}"
        await page.launch_url_async(url) if hasattr(page, 'launch_url_async') else page.launch_url(url)

    async def abrir_google_maps(endereco):
        url_maps = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(endereco)}"
        await page.launch_url_async(url_maps) if hasattr(page, 'launch_url_async') else page.launch_url(url_maps)

    async def exibir_snackbar(mensagem):
        snack = ft.SnackBar(
            content=ft.Text(mensagem, weight=ft.FontWeight.BOLD, color="white"), 
            bgcolor=COR_PRINCIPAL, 
            duration=3000
        )
        page.open(snack)
        await page.update_async() if hasattr(page, 'update_async') else page.update()

    async def mudar_tela(novo_conteudo):
        page.clean()
        page.add(novo_conteudo)
        await page.update_async() if hasattr(page, 'update_async') else page.update()

    # --- SESSÃO ---
    def salvar_sessao(cpf):
        dados = {"cpf": cpf, "logado": True, "timestamp": time.time()}
        try:
            with open(ARQUIVO_SESSAO, "w") as f:
                json.dump(dados, f)
        except Exception as e:
            print(f"Erro ao salvar sessão: {e}", flush=True)

    async def encerrar_sessao(e=None):
        if os.path.exists(ARQUIVO_SESSAO):
            os.remove(ARQUIVO_SESSAO)
        await exibir_snackbar("Sessão encerrada.")
        await mostrar_tela_login()

    async def processar_pos_login(cpf_usuario):
        salvar_sessao(cpf_usuario)
        await mostrar_menu_inicial(None)

    # =========================================================================
    # 1️⃣ TELA DE LOGIN
    # =========================================================================
    async def mostrar_tela_login():
        txt_erro = ft.Text("", color=ft.Colors.RED_600, size=13, weight=ft.FontWeight.BOLD)
        campo_cpf = ft.TextField(label="Digite seu CPF", hint_text="000.000.000-00", width=300, border_radius=12, border_color=COR_PRINCIPAL)
        campo_senha = ft.TextField(label="Digite sua Senha", password=True, can_reveal_password=True, width=300, border_radius=12, border_color=COR_PRINCIPAL)

        async def formatar_cpf(e):
            apenas_numeros = "".join([c for c in campo_cpf.value if c.isdigit()])[:11]
            if len(apenas_numeros) <= 3: campo_cpf.value = apenas_numeros
            elif len(apenas_numeros) <= 6: campo_cpf.value = f"{apenas_numeros[:3]}.{apenas_numeros[3:]}"
            elif len(apenas_numeros) <= 9: campo_cpf.value = f"{apenas_numeros[:3]}.{apenas_numeros[3:6]}.{apenas_numeros[6:]}"
            else: campo_cpf.value = f"{apenas_numeros[:3]}.{apenas_numeros[3:6]}.{apenas_numeros[6:9]}-{apenas_numeros[9:]}"
            await page.update_async() if hasattr(page, 'update_async') else page.update()

        campo_cpf.on_change = formatar_cpf

        async def realizar_login(e):
            if campo_cpf.value == CPF_TESTE and campo_senha.value == SENHA_TESTE:
                await processar_pos_login(campo_cpf.value)
            else:
                txt_erro.value = "CPF ou Senha incorretos!"
                await page.update_async() if hasattr(page, 'update_async') else page.update()

        async def autenticar_biometria(e):
            await exibir_snackbar("👆 Autenticando por Biometria / Face ID...")
            time.sleep(0.8)
            await processar_pos_login(CPF_TESTE)

        btn_entrar = ft.FilledButton(
            content=ft.Text("Entrar na Área do Cliente", color="white", weight=ft.FontWeight.BOLD),
            width=300, height=48,
            style=ft.ButtonStyle(bgcolor=COR_PRINCIPAL, shape=ft.RoundedRectangleBorder(radius=12)),
            on_click=realizar_login
        )

        btn_biometria = ft.OutlinedButton(
            content=ft.Row([
                ft.Icon(ft.Icons.FINGERPRINT, color=COR_PRINCIPAL, size=22),
                ft.Text("Entrar com Biometria / Face ID", color=COR_PRINCIPAL, weight=ft.FontWeight.BOLD, size=12)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            width=300, height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
            on_click=autenticar_biometria
        )

        divisoria_linha = ft.Container(width=100, height=1, bgcolor="grey400")

        conteudo = ft.Container(
            content=ft.Column([
                ft.Row([ft.IconButton(icon=ft.Icons.DARK_MODE_OUTLINED, on_click=alternar_tema)], alignment=ft.MainAxisAlignment.END),
                ft.Text("🏥", size=45), 
                ft.Text("Plano Viver", size=30, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL), 
                ft.Container(height=5), campo_cpf, campo_senha, txt_erro, 
                ft.Container(height=5), btn_entrar, 
                ft.Row([divisoria_linha, ft.Text("ou", color="grey500", size=11), divisoria_linha], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                btn_biometria
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16, padding=10
        )
        await mudar_tela(conteudo)

    # =========================================================================
    # 2️⃣ TELA DE AVISOS / NOTIFICAÇÕES
    # =========================================================================
    async def mostrar_tela_notificacoes(e=None):
        dados_notificacoes = [
            {
                "icone": "⚠️", "titulo": "Atenção ao Boleto", 
                "mensagem": "Seu boleto mensal está disponível. Pague via PIX sem taxas.", "data": "Hoje",
                "acao_texto": "💳 Pagar Agora", "acao": abrir_tela_boletos
            },
            {
                "icone": "🩺", "titulo": "Consulta Confirmada", 
                "mensagem": "Sua última consulta foi registrada com sucesso no sistema.", "data": "Ontem",
                "acao_texto": "📋 Ver Histórico", "acao": abrir_tela_historico
            }
        ]

        lista_avisos = ft.ListView(expand=1, spacing=10, padding=5)
        for notif in dados_notificacoes:
            card_notif = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(notif["icone"], size=24), 
                        ft.Column([
                            ft.Row([ft.Text(notif["titulo"], weight=ft.FontWeight.BOLD, size=14, color=COR_PRINCIPAL), ft.Text(notif["data"], size=10, color="grey500")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=240), 
                            ft.Text(notif["mensagem"], size=12, color="grey700", width=240)
                        ])
                    ]),
                    ft.Row([
                        ft.TextButton(
                            content=ft.Text(notif["acao_texto"], size=11, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL),
                            on_click=notif["acao"]
                        )
                    ], alignment=ft.MainAxisAlignment.END)
                ], spacing=5), 
                border_radius=12, padding=12, border=ft.Border.all(width=1, color="#E2E8F0"), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
            )
            lista_avisos.controls.append(card_notif)

        conteudo = ft.Container(
            content=ft.Column([
                ft.Text("🔔 Central de Avisos", size=22, color=COR_PRINCIPAL, weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                ft.Container(content=lista_avisos, width=340, height=480), 
                ft.TextButton("Voltar para o Menu", icon=ft.Icons.ARROW_BACK, on_click=mostrar_menu_inicial)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(conteudo)

    # --- TELA: PAINEL DE ECONOMIA (TERCEIRA TELA DEDICADA) ---
    async def abrir_tela_economia(e=None):
        total_pago = sum(c["valor"] for c in dados_historico_consultas)
        total_particular = sum(c["particular"] for c in dados_historico_consultas)
        total_economizado = total_particular - total_pago
        porcentagem_economia = (total_economizado / total_particular) * 100 if total_particular > 0 else 0

        card_resumo = ft.Container(
            content=ft.Column([
                ft.Text("SUA ECONOMIA EM 2026", size=11, color=ft.Colors.WHITE_70, weight=ft.FontWeight.W_500),
                ft.Text(f"R$ {total_economizado:.2f}", size=32, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text(f"Você economizou {porcentagem_economia:.0f}% em relação à rede particular!", size=11, color=COR_BORDA_GOLD, weight=ft.FontWeight.BOLD),
                ft.Divider(height=15, color=ft.Colors.WHITE_24),
                ft.Row([
                    ft.Column([
                        ft.Text("Valor Particular", size=10, color=ft.Colors.WHITE_70),
                        ft.Text(f"R$ {total_particular:.2f}", size=13, color="white", weight=ft.FontWeight.BOLD)
                    ]),
                    ft.Column([
                        ft.Text("Pago pelo Plano Viver", size=10, color=ft.Colors.WHITE_70),
                        ft.Text(f"R$ {total_pago:.2f}", size=13, color="white", weight=ft.FontWeight.BOLD)
                    ])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=5),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[COR_PRINCIPAL, COR_GRADIENT_FIM]
            ),
            padding=18, border_radius=16, width=340,
            shadow=ft.BoxShadow(blur_radius=8, color="grey300", offset=ft.Offset(0, 4))
        )

        lista_detalhada = ft.ListView(expand=1, spacing=10, padding=5)
        for c in dados_historico_consultas:
            economia_item = c["particular"] - c["valor"]
            card_item = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(c["especialidade"], weight=ft.FontWeight.BOLD, size=13, color=COR_PRINCIPAL),
                        ft.Text(f"Economia: R$ {economia_item:.2f}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(f"Local: {c['local']}", size=11, color="grey700"),
                    ft.Row([
                        ft.Text(f"Particular: R$ {c['particular']:.2f}", size=10, color="grey500"),
                        ft.Text(f"Preço Viver: R$ {c['valor']:.2f}", size=10, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=3),
                padding=12, border_radius=12, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border=ft.Border.all(1, "#E2E8F0")
            )
            lista_detalhada.controls.append(card_item)

        conteudo = ft.Container(
            content=ft.Column([
                ft.Text("📈 Economia com o Plano", size=22, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL),
                ft.Container(height=5),
                card_resumo,
                ft.Container(height=10),
                ft.Text("Detalhamento por Atendimento:", size=13, weight=ft.FontWeight.BOLD, color="grey800"),
                ft.Container(content=lista_detalhada, width=340, height=330),
                ft.TextButton("Voltar para Histórico", icon=ft.Icons.ARROW_BACK, on_click=abrir_tela_historico)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(conteudo)

    # --- TELA SELEÇÃO DE PERFIL COM INCLUSÃO DE DEPENDENTES ---
    async def mostrar_tela_perfis(e=None):
        async def selecionar_perfil(chave, nome):
            perfil_atual["chave"], perfil_atual["nome"] = chave, nome
            await mostrar_menu_inicial(None)

        async def abrir_modal_novo_dependente(e):
            campo_nome_dep = ft.TextField(label="Nome do Dependente", border_color=COR_PRINCIPAL)
            dropdown_parentesco = ft.Dropdown(
                label="Parentesco",
                options=[
                    ft.dropdown.Option("Filho(a)"),
                    ft.dropdown.Option("Cônjuge"),
                    ft.dropdown.Option("Pai/Mãe"),
                    ft.dropdown.Option("Outro")
                ],
                border_color=COR_PRINCIPAL
            )

            async def fechar_modal_dep(e):
                bs_dependente.open = False
                await page.update_async() if hasattr(page, 'update_async') else page.update()

            async def salvar_dependente(e):
                if campo_nome_dep.value:
                    novo_id = f"dep_{len(dados_carteirinhas)}"
                    nome_formatado = f"{campo_nome_dep.value.upper()} (DEP)"
                    dados_carteirinhas[novo_id] = {
                        "nome": nome_formatado,
                        "numero": f"001.2345.678900-{15 + len(dados_carteirinhas)}",
                        "plano": "VIVER GLOBAL (PLANO PRATA)",
                        "validade": "12/2028",
                        "avatar": "🧑",
                        "status": "ATIVO",
                        "vencimento": "10/08/2026"
                    }
                    await salvar_carteirinhas_localment()
                    await fechar_modal_dep(e)
                    await exibir_snackbar(f"✅ Dependente {campo_nome_dep.value} adicionado com sucesso!")
                    await mostrar_tela_perfis()

            bs_dependente = ft.BottomSheet(
                content=ft.Container(
                    padding=20,
                    content=ft.Column([
                        ft.Text("➕ Adicionar Novo Dependente", size=18, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL),
                        campo_nome_dep,
                        dropdown_parentesco,
                        ft.FilledButton("Cadastrar Dependente", style=ft.ButtonStyle(bgcolor=COR_PRINCIPAL), on_click=salvar_dependente),
                        ft.TextButton("Cancelar", on_click=fechar_modal_dep)
                    ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
            page.open(bs_dependente)
            await page.update_async() if hasattr(page, 'update_async') else page.update()

        grid = ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Container(content=ft.Text(v["avatar"], size=35), width=75, height=75, border_radius=20, border=ft.Border.all(width=2, color=COR_PRINCIPAL), alignment=ft.Alignment(0, 0)), 
                    ft.Text(v["nome"].split()[0], size=11, weight=ft.FontWeight.BOLD)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER), 
                on_click=lambda e, k=k, n=v["nome"]: selecionar_perfil(k, n)
            ) for k, v in dados_carteirinhas.items()
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10, wrap=True)

        conteudo = ft.Container(
            content=ft.Column([
                ft.Text("🏥 Plano Viver", size=24, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL), 
                ft.Container(height=10), 
                ft.Text("Quem está utilizando o app agora?", size=14, color="grey700"), 
                ft.Container(height=10), grid,
                ft.Container(height=15),
                ft.OutlinedButton("➕ Solicitar Novo Dependente", on_click=abrir_modal_novo_dependente),
                ft.Container(height=10),
                ft.TextButton("Voltar para o Menu", icon=ft.Icons.ARROW_BACK, on_click=mostrar_menu_inicial)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(conteudo)

    # =========================================================================
    # 3️⃣ TELA: MENU PRINCIPAL (BANNER DE ECONOMIA REMOVIDO DAQUI)
    # =========================================================================
    async def mostrar_menu_inicial(e=None):
        primeiro_nome = perfil_atual["nome"].split()[0].title()
        
        # Leitura segura dos dados das carteirinhas
        dados_carteirinhas_loc = await page.shared_preferences.get("dados_carteirinhas") if await page.shared_preferences.contains_key("dados_carteirinhas") else dados_carteirinhas
        if not isinstance(dados_carteirinhas_loc, dict):
            dados_carteirinhas_loc = dados_carteirinhas
            
        dados_p = dados_carteirinhas_loc.get(perfil_atual["chave"], dados_carteirinhas_loc.get("titular"))

        icone_sininho = ft.Stack([
            ft.IconButton(icon=ft.Icons.NOTIFICATIONS_OUTLINED, icon_color="white", on_click=mostrar_tela_notificacoes, tooltip="Avisos"),
            ft.Container(
                content=ft.Container(width=8, height=8, bgcolor=ft.Colors.RED_500, border_radius=4),
                right=10, top=10
            )
        ])

        topo_verde = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("APP VIVER", color=ft.Colors.WHITE_70, size=10, weight=ft.FontWeight.W_500), 
                    ft.Row([
                        ft.Text("viver", size=28, weight=ft.FontWeight.BOLD, color="white", italic=True), 
                        ft.Text("✨", size=16)
                    ])
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([
                    icone_sininho,
                    ft.IconButton(icon=ft.Icons.DARK_MODE_OUTLINED, icon_color="white", on_click=alternar_tema)
                ], spacing=0)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), 
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[COR_PRINCIPAL, COR_GRADIENT_FIM]
            ), 
            width=390, height=90, padding=ft.Padding(20, 0, 10, 0),
            border_radius=ft.BorderRadius(top_left=16, top_right=16, bottom_left=0, bottom_right=0)
        )

        card_status_plano = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Container(width=10, height=10, bgcolor=ft.Colors.GREEN_500, border_radius=5),
                    ft.Column([
                        ft.Row([
                            ft.Text("PLANO", size=9, color="grey600", weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=ft.Text(dados_p["status"], size=9, weight=ft.FontWeight.BOLD, color="white"),
                                bgcolor=ft.Colors.GREEN_700, padding=ft.Padding(4, 1, 4, 1), border_radius=4
                            )
                        ], spacing=5),
                        ft.Text(dados_p["plano"], size=10.5, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL),
                    ], spacing=1)
                ], spacing=8),
                ft.Column([
                    ft.Text("Próx. Vencimento", size=8.5, color="grey600"),
                    ft.Text(dados_p.get("vencimento", "10/08/2026"), size=10, weight=ft.FontWeight.BOLD, color="grey800")
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.END)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor="white", padding=ft.Padding(12, 8, 12, 8), border_radius=12, width=350,
            border=ft.Border.all(width=1, color="#CBD5E1"),
            shadow=ft.BoxShadow(blur_radius=4, color="grey200", offset=ft.Offset(0, 2))
        )

        texto_saudacao = ft.Container(
            content=ft.Column([
                ft.Text(f"Seja bem vindo(a), {primeiro_nome}! 👋", size=17, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL), 
                ft.Text("Como podemos ajudar você hoje?", size=11.5, color="grey700")
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER), 
            padding=0
        )

        def criar_cartao_menu_2colunas(icone, titulo, subtexto, acao_click, destacar=False):
            sombra_padrao = ft.BoxShadow(blur_radius=6, spread_radius=1, color="grey200", offset=ft.Offset(0, 4))
            return ft.Container(
                content=ft.Column([
                    ft.Icon(icone, size=30, color="white" if destacar else COR_PRINCIPAL), 
                    ft.Text(titulo, size=11.5, weight=ft.FontWeight.BOLD, color="white" if destacar else COR_PRINCIPAL, text_align=ft.TextAlign.CENTER),
                    ft.Text(subtexto, size=9, color=ft.Colors.WHITE_70 if destacar else "grey600", text_align=ft.TextAlign.CENTER)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2), 
                width=165, height=105, 
                bgcolor=COR_PRINCIPAL if destacar else "white", 
                border_radius=14, 
                border=ft.Border.all(width=1.5, color=COR_BORDA_GOLD if destacar else "#E2E8F0"),
                shadow=sombra_padrao,
                on_click=acao_click
            )

        grid_botoes = ft.Column([
            ft.Row([
                criar_cartao_menu_2colunas(ft.Icons.SUPPORT_AGENT, "Assistente Saúde", "Fale no WhatsApp", lambda e: abrir_whatsapp(e, "assistente"), destacar=True), 
                criar_cartao_menu_2colunas(ft.Icons.MONETIZATION_ON, "Meus Boletos", "Faturas e PIX", abrir_tela_boletos)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
            ft.Row([
                criar_cartao_menu_2colunas(ft.Icons.CARD_MEMBERSHIP, "Carteirinha", "Digital & Offline", abrir_tela_carteirinha), 
                criar_cartao_menu_2colunas(ft.Icons.NOTIFICATIONS_ACTIVE, "Avisos & Alertas", "Minhas Notificações", mostrar_tela_notificacoes)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
            ft.Row([
                criar_cartao_menu_2colunas(ft.Icons.FACT_CHECK, "Rede Credenciada", "Buscar Clínicas", abrir_tela_rede),
                criar_cartao_menu_2colunas(ft.Icons.HISTORY, "Histórico Consultas", "Minhas Utilizações", abrir_tela_historico)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=15)
        ], spacing=12)

        barra_inferior = ft.Container(
            content=ft.Row([
                ft.IconButton(icon=ft.Icons.CREDIT_CARD, icon_color=COR_PRINCIPAL, on_click=abrir_tela_carteirinha, tooltip="Carteirinha"), 
                ft.IconButton(icon=ft.Icons.CHAT_BUBBLE, icon_color=COR_PRINCIPAL, on_click=lambda e: abrir_whatsapp(e, "suporte"), tooltip="Atendimento"), 
                ft.IconButton(icon=ft.Icons.SUPERVISOR_ACCOUNT, icon_color=COR_PRINCIPAL, on_click=mostrar_tela_perfis, tooltip="Trocar Perfil"), 
                ft.IconButton(icon=ft.Icons.LOGOUT, icon_color=ft.Colors.RED_600, on_click=encerrar_sessao, tooltip="Sair")
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND), 
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, height=55, width=390,
            border_radius=ft.BorderRadius(top_left=0, top_right=0, bottom_left=16, bottom_right=16)
        )
        
        layout_celular = ft.Container(
            content=ft.Column([
                topo_verde, 
                ft.Container(
                    content=ft.Column([
                        card_status_plano,
                        texto_saudacao, 
                        grid_botoes
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15), 
                    expand=True
                ), 
                barra_inferior
            ], spacing=0, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(layout_celular)

    # =========================================================================
    # 4️⃣ TELA: CARTEIRINHA DIGITAL
    # =========================================================================
    async def abrir_tela_carteirinha(e=None):
        dados_carteirinhas_loc = await page.shared_preferences.get("dados_carteirinhas") if await page.shared_preferences.contains_key("dados_carteirinhas") else dados_carteirinhas
        if not isinstance(dados_carteirinhas_loc, dict):
            dados_carteirinhas_loc = dados_carteirinhas

        dados = dados_carteirinhas_loc.get(perfil_atual["chave"], dados_carteirinhas_loc.get("titular"))
        mostrando_frente = [True]

        degrade_carteirinha = ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[COR_PRINCIPAL, COR_GRADIENT_FIM, "#003D37"]
        )

        # LADO A: FRENTE
        frente_ui = ft.Container(
            key="frente_card",
            content=ft.Column([
                ft.Row([
                    ft.Text("VIVER SAÚDE", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Icon(ft.Icons.CONTACTLESS, color="white", size=24)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=5),
                ft.Container(width=40, height=28, bgcolor="#D4AF37", border_radius=5),
                ft.Text(dados["nome"], size=15, weight=ft.FontWeight.BOLD, color="white"), 
                ft.Text(dados["numero"], size=15, color="white", weight=ft.FontWeight.W_500), 
                ft.Row([
                    ft.Text(dados["plano"], size=10, color=ft.Colors.WHITE_70),
                    ft.Text(f"VAL: {dados['validade']}", size=10, color=ft.Colors.WHITE_70)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            gradient=degrade_carteirinha,
            width=340, height=195, border_radius=16, padding=18,
            shadow=ft.BoxShadow(blur_radius=12, color="grey400", offset=ft.Offset(0, 6))
        )

        # LADO B: VERSO
        verso_ui = ft.Container(
            key="verso_card",
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.HEADSET_MIC, color=COR_BORDA_GOLD, size=18),
                    ft.Text("CENTRAL DE COMUNICAÇÕES", size=11, weight=ft.FontWeight.BOLD, color="white")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                ft.Divider(height=1, color=ft.Colors.WHITE_24),
                ft.Column([
                    ft.Row([
                        ft.Text("3003-6773", size=11, weight=ft.FontWeight.BOLD, color=COR_BORDA_GOLD),
                        ft.Text("• funeral em capitais e metropolitanas", size=8.5, color="white")
                    ], spacing=4),
                    ft.Row([
                        ft.Text("0800 709 8059", size=11, weight=ft.FontWeight.BOLD, color=COR_BORDA_GOLD),
                        ft.Text("• funeral em demais localidades", size=8.5, color="white")
                    ], spacing=4),
                    ft.Row([
                        ft.Text("(47) 3033-8008", size=11, weight=ft.FontWeight.BOLD, color=COR_BORDA_GOLD),
                        ft.Text("• atendimento geral", size=8.5, color="white")
                    ], spacing=4),
                ], spacing=5),
                ft.Row([
                    ft.Text("Plano Viver Saúde • Informações e Suporte", size=8, color=ft.Colors.WHITE_70)
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            gradient=degrade_carteirinha,
            width=340, height=195, border_radius=16, padding=16,
            shadow=ft.BoxShadow(blur_radius=12, color="grey400", offset=ft.Offset(0, 6))
        )

        cartao_animado = ft.AnimatedSwitcher(
            content=frente_ui,
            transition=ft.AnimatedSwitcherTransition.SCALE,
            duration=400,
            reverse_duration=400,
            switch_in_curve=ft.AnimationCurve.EASE_IN_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN_OUT
        )

        async def girar_cartao_animado(e):
            mostrando_frente[0] = not mostrando_frente[0]
            cartao_animado.content = frente_ui if mostrando_frente[0] else verso_ui
            await page.update_async() if hasattr(page, 'update_async') else page.update()

        async def baixar_carteirinha_pdf(e):
            try:
                dados_c = dados
                nome_arquivo = f"carteirinha_{perfil_atual['chave']}.pdf"
                caminho_completo = os.path.join(PASTA_PDFS, nome_arquivo)

                doc = SimpleDocTemplate(
                    caminho_completo, 
                    pagesize=A4, 
                    rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
                )
                styles = getSampleStyleSheet()
                
                estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#005F56"), alignment=1, spaceAfter=15)
                estilo_sub = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.gray, alignment=1, spaceAfter=20)
                estilo_rotulo = ParagraphStyle('Rotulo', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#005F56"), fontName="Helvetica-Bold")
                estilo_valor = ParagraphStyle('Valor', parent=styles['Normal'], fontSize=11, textColor=colors.black, fontName="Helvetica-Bold")
                estilo_rodape = ParagraphStyle('Rodape', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=1)

                elementos = [
                    Paragraph("<b>PLANO VIVER SAÚDE</b>", estilo_titulo),
                    Paragraph("Carteirinha Digital do Beneficiário", estilo_sub),
                    Spacer(1, 10)
                ]

                tabela_dados = [
                    [Paragraph("NOME DO BENEFICIÁRIO:", estilo_rotulo), Paragraph(dados_c["nome"], estilo_valor)],
                    [Paragraph("NÚMERO DA CARTEIRINHA:", estilo_rotulo), Paragraph(dados_c["numero"], estilo_valor)],
                    [Paragraph("PLANO:", estilo_rotulo), Paragraph(dados_c["plano"], estilo_valor)],
                    [Paragraph("VALIDADE:", estilo_rotulo), Paragraph(dados_c["validade"], estilo_valor)],
                ]

                t_card = Table(tabela_dados, colWidths=[160, 280])
                t_card.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
                    ('PADDING', (0,0), (-1,-1), 10),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor("#CBD5E1")),
                    ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor("#005F56")),
                ]))
                
                elementos.append(t_card)
                elementos.append(Spacer(1, 25))
                elementos.append(Paragraph("<b>CENTRAL DE ATENDIMENTO E SUPORTE</b>", estilo_rotulo))
                elementos.append(Spacer(1, 5))
                
                tabela_suporte = [
                    [Paragraph("Capitais e Regiões Metropolitanas:", estilo_rotulo), Paragraph("3003-6773", estilo_valor)],
                    [Paragraph("Demais Localidades (Funeral):", estilo_rotulo), Paragraph("0800 709 8059", estilo_valor)],
                    [Paragraph("Atendimento Geral Viver:", estilo_rotulo), Paragraph("(47) 3033-8008", estilo_valor)],
                ]
                t_sup = Table(tabela_suporte, colWidths=[180, 260])
                t_sup.setStyle(TableStyle([('PADDING', (0,0), (-1,-1), 6)]))
                
                elementos.append(t_sup)
                elementos.append(Spacer(1, 30))
                elementos.append(Paragraph("Documento gerado digitalmente pelo aplicativo Plano Viver.", estilo_rodape))

                doc.build(elementos)

                await page.launch_url_async(f"/static/{nome_arquivo}") if hasattr(page, 'launch_url_async') else page.launch_url(f"/static/{nome_arquivo}")
                await exibir_snackbar("✅ Carteirinha gerada! Baixando...")

            except Exception as err:
                print(f"Erro PDF: {err}", flush=True)
                await exibir_snackbar("❌ Erro ao gerar PDF. Verifique os módulos instalados.")

        conteudo = ft.Container(
            content=ft.Column([
                ft.Text("💳 Carteirinha Digital", size=24, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL), 
                ft.Container(height=10), 
                cartao_animado,
                ft.Container(height=15),
                ft.Row([
                    ft.OutlinedButton("🔄 Virar Cartão", on_click=girar_cartao_animado),
                    ft.ElevatedButton("📥 Baixar PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=baixar_carteirinha_pdf)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ft.Container(height=10), 
                ft.TextButton("Voltar", icon=ft.Icons.ARROW_BACK, on_click=mostrar_menu_inicial)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(conteudo)

    # --- HISTÓRICO DE CONSULTAS (COM A NOVA ABA DE ECONOMIA) ---
    async def abrir_tela_historico(e=None):
        total_pago = sum(c["valor"] for c in dados_historico_consultas)
        total_particular = sum(c["particular"] for c in dados_historico_consultas)
        total_economizado = total_particular - total_pago

        # Aba/Banner compacto de economia inserido no topo
        aba_economia = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.SAVINGS, color=ft.Colors.GREEN_800, size=20),
                    ft.Column([
                        ft.Text("Sua Economia em 2026", weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.GREEN_900),
                        ft.Text(f"Total poupado: R$ {total_economizado:.2f}", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)
                    ], spacing=0)
                ], spacing=8),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ft.Colors.GREEN_800, size=20)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor="#E8F5E9", padding=ft.Padding(12, 8, 12, 8), border_radius=10, width=340,
            border=ft.Border.all(width=1, color="#A5D6A7"),
            on_click=abrir_tela_economia
        )

        lista_consultas = ft.ListView(expand=1, spacing=10, padding=5)

        for c in dados_historico_consultas:
            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"🩺 {c['especialidade']}", weight=ft.FontWeight.BOLD, size=14, color=COR_PRINCIPAL),
                        ft.Container(content=ft.Text(c['status'], color="white", size=9, weight=ft.FontWeight.BOLD), bgcolor=ft.Colors.GREEN_700, padding=4, border_radius=4)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(f"Médico: {c['medico']}", size=12, color="grey800"),
                    ft.Text(f"Local: {c['local']}", size=11, color="grey600"),
                    ft.Divider(height=5, color="grey200"),
                    ft.Row([
                        ft.Text(f"Data: {c['data']}", size=11, color="grey600"),
                        ft.Text(f"Valor Pago: R$ {c['valor']:.2f}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=3),
                border_radius=12, padding=12, border=ft.Border.all(width=1, color="#E2E8F0"), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                shadow=ft.BoxShadow(blur_radius=5, color="grey200", offset=ft.Offset(0, 3))
            )
            lista_consultas.controls.append(card)

        conteudo = ft.Container(
            content=ft.Column([
                ft.Text("📋 Histórico de Consultas", size=22, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL),
                ft.Container(height=5),
                aba_economia,
                ft.Container(height=5),
                ft.Container(content=lista_consultas, width=340, height=390),
                ft.TextButton("Voltar para o Menu", icon=ft.Icons.ARROW_BACK, on_click=mostrar_menu_inicial)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(conteudo)

    # =========================================================================
    # 5️⃣ TELA: REDE CREDENCIADA (COM INTEGRAÇÃO MAPS/GPS)
    # =========================================================================
    async def abrir_tela_rede(e=None):
        lista_locais = ft.ListView(expand=1, spacing=10, padding=5)

        locais_planilha = [
            {"nome": "Nova Medical Center", "categoria": "Cirurgias", "bairro": "Bom Retiro", "esp": "Cirurgia Bariátrica / Geral", "end": "Avenida Rolf Wiest, 333 - Bom Retiro, Joinville - SC", "tel": "(47) 3842-3978", "valor": "R$ 200,00"},
            {"nome": "Instituto de Cirurgia Joinville", "categoria": "Cirurgias", "bairro": "Centro", "esp": "Cirurgia Geral / Mastologia", "end": "Rua Mário Lobo, 61 - Centro, Joinville - SC", "tel": "(47) 3422-1602", "valor": "R$ 180,00"},
            {"nome": "Clínica Voe Saúde", "categoria": "Consultas", "bairro": "Aventureiro", "esp": "Cardiologia / Clínico / Gastro", "end": "Rua Tuiuti, 2295 - Aventureiro, Joinville - SC", "tel": "(47) 3305-8999", "valor": "R$ 180,00 a R$ 250,00"},
            {"nome": "Clínica Atend Já", "categoria": "Consultas", "bairro": "Centro", "esp": "Cardiologia / Dermato / Oftalmo", "end": "Rua Alexandre Döhler, 331 - Centro, Joinville - SC", "tel": "(47) 9154-7004", "valor": "R$ 110,00 a R$ 145,00"},
            {"nome": "Prontocor Clínica", "categoria": "Consultas", "bairro": "América", "esp": "Cardiologia / Eletrocardiograma", "end": "Rua Quinze de Novembro, 867 - América, Joinville - SC", "tel": "(47) 3422-5555", "valor": "R$ 230,00"},
            {"nome": "OdontoViver Clínica Dental", "categoria": "Dentista", "bairro": "Costa e Silva", "esp": "Limpeza / Restauração / Canal / Aparelho", "end": "Rua Otto Pfuetzenreuter, 450 - Costa e Silva, Joinville - SC", "tel": "(47) 3435-1212", "valor": "Desconto de até 40%"},
            {"nome": "Sorriso Real Odontologia", "categoria": "Dentista", "bairro": "Floresta", "esp": "Implantes / Odontopediatria", "end": "Rua Santa Catarina, 1200 - Floresta, Joinville - SC", "tel": "(47) 3455-8899", "valor": "Desconto de até 35%"},
            {"nome": "Laboratório Gimenes Exames", "categoria": "Exames", "bairro": "Anita Garibaldi", "esp": "Sangue / Urina / Exames de Imagem", "end": "Rua São Firmino, 210 - Anita Garibaldi, Joinville - SC", "tel": "(47) 3028-9900", "valor": "Tabela Especial Viver"},
            {"nome": "Farmácia São João Credenciada", "categoria": "Farmácia", "bairro": "Vila Nova", "esp": "Medicamentos com desconto do plano", "end": "Rua XV de Novembro, 7000 - Vila Nova, Joinville - SC", "tel": "(47) 3439-0011", "valor": "Até 30% em remédios"},
            {"nome": "Drogaria Catarinense", "categoria": "Farmácia", "bairro": "Iririú", "esp": "Farmácia Parceira Viver", "end": "Rua Iririú, 2300 - Iririú, Joinville - SC", "tel": "(47) 3427-4400", "valor": "Desconto na hora no CPF"}
        ]

        async def renderizar_lista(e=None):
            lista_locais.controls.clear()
            termo = campo_pesquisa.value.lower() if campo_pesquisa.value else ""
            bairro_filtro = dropdown_bairro.value
            cat_filtro = dropdown_categoria.value

            for local in locais_planilha:
                bateu_texto = termo in (local["nome"] + " " + local["esp"] + " " + local["end"]).lower()
                bateu_bairro = (bairro_filtro == "Todos os bairros") or (local["bairro"] == bairro_filtro)
                bateu_cat = (cat_filtro == "Todas as categorias") or (local["categoria"] == cat_filtro)

                if bateu_texto and bateu_bairro and bateu_cat:
                    card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Row([ft.Text("🩺", size=15), ft.Text(local["nome"], weight=ft.FontWeight.BOLD, size=12.5, color=COR_PRINCIPAL)]),
                                ft.Container(content=ft.Text(local["bairro"], size=8.5, color=COR_PRINCIPAL, weight=ft.FontWeight.BOLD), bgcolor="#E0F2FE", padding=ft.Padding(5,2,5,2), border_radius=4)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(f"Especialidades: {local['esp']}", size=10.5, color="grey700"),
                            ft.Row([ft.Icon(ft.Icons.MONETIZATION_ON, size=13, color=ft.Colors.GREEN_700), ft.Text(f"Valor Viver: {local['valor']}", size=10.5, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)]),
                            ft.Divider(height=4, color="grey200"),
                            ft.Row([ft.Icon(ft.Icons.LOCATION_ON, size=12, color="grey500"), ft.Text(local["end"], size=9.5, color="grey500", width=240)]),
                            
                            ft.Row([
                                ft.TextButton(
                                    content=ft.Row([ft.Icon(ft.Icons.MAP, size=12, color=COR_PRINCIPAL), ft.Text("📍 Como Chegar", size=10.5, color=COR_PRINCIPAL)]), 
                                    on_click=lambda e, end=local["end"]: abrir_google_maps(end)
                                ),
                                ft.TextButton(
                                    content=ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH, size=12, color="grey600"), ft.Text("Agendar", size=10.5, color="grey600")]), 
                                    on_click=lambda e: abrir_whatsapp(e, "assistente")
                                )
                            ], alignment=ft.MainAxisAlignment.END, spacing=5)
                        ], spacing=3),
                        border_radius=12, padding=10, border=ft.Border.all(width=1, color="#E2E8F0"), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        shadow=ft.BoxShadow(blur_radius=4, color="grey200", offset=ft.Offset(0, 2))
                    )
                    lista_locais.controls.append(card)

            if len(lista_locais.controls) == 0:
                lista_locais.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.LOCATION_OFF, size=35, color="grey400"),
                            ft.Text("Nenhum local encontrado para os filtros selecionados.", size=11, color="grey600", text_align=ft.TextAlign.CENTER)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=20
                    )
                )

            try:
                await page.update_async() if hasattr(page, 'update_async') else page.update()
            except Exception:
                pass

        campo_pesquisa = ft.TextField(
            hint_text="Buscar clínica, médico...", 
            prefix_icon=ft.Icons.SEARCH, border_radius=10, border_color=COR_PRINCIPAL, 
            width=340, height=40, content_padding=8, 
            on_change=renderizar_lista
        )

        dropdown_bairro = ft.Dropdown(
            label="Bairro",
            value="Todos os bairros",
            width=165,
            border_radius=10,
            border_color=COR_PRINCIPAL,
            options=[
                ft.dropdown.Option("Todos os bairros"),
                ft.dropdown.Option("Centro"),
                ft.dropdown.Option("Aventureiro"),
                ft.dropdown.Option("Bom Retiro"),
                ft.dropdown.Option("Floresta"),
                ft.dropdown.Option("Costa e Silva"),
                ft.dropdown.Option("América"),
                ft.dropdown.Option("Anita Garibaldi"),
                ft.dropdown.Option("Vila Nova"),
                ft.dropdown.Option("Iririú"),
            ]
        )
        dropdown_bairro.on_change = renderizar_lista

        dropdown_categoria = ft.Dropdown(
            label="Categoria",
            value="Todas as categorias",
            width=165,
            border_radius=10,
            border_color=COR_PRINCIPAL,
            options=[
                ft.dropdown.Option("Todas as categorias"),
                ft.dropdown.Option("Consultas"),
                ft.dropdown.Option("Exames"),
                ft.dropdown.Option("Dentista"),
                ft.dropdown.Option("Farmácia"),
                ft.dropdown.Option("Cirurgias"),
            ]
        )
        dropdown_categoria.on_change = renderizar_lista

        painel_filtros = ft.Column([
            campo_pesquisa,
            ft.Row([
                dropdown_bairro,
                dropdown_categoria
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
        ], spacing=8, width=340)

        await renderizar_lista()

        conteudo = ft.Container(
            content=ft.Column([
                ft.Text("📍 Rede Credenciada", size=22, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL), 
                painel_filtros, 
                ft.Container(content=lista_locais, width=340, height=390), 
                ft.TextButton("Voltar para o Menu", icon=ft.Icons.ARROW_BACK, on_click=mostrar_menu_inicial)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        
        await mudar_tela(conteudo)

    # =========================================================================
    # 6️⃣ TELA: BOLETOS & ASAAS
    # =========================================================================
    async def abrir_tela_boletos(e=None):
        progresso = ft.ProgressRing(color=COR_PRINCIPAL)
        carregando = ft.Container(
            content=ft.Column([
                progresso, 
                ft.Text("Buscando faturas no Asaas...", italic=True)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, 
            shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(carregando)

        faturas_asaas = obtener_boletos_asaas(CPF_TESTE, perfil_atual["nome"])
        lista_cards = []

        async def copiar_texto(texto, msg):
            await page.set_clipboard_async(texto) if hasattr(page, 'set_clipboard_async') else page.set_clipboard(texto)
            await exibir_snackbar(msg)

        async def abrir_modal_pix(fatura_id, valor):
            pix_dados = obtener_pix_asaas(fatura_id)
            if pix_dados and pix_dados.get("payload"):
                payload_pix = pix_dados["payload"]
                qr_base64 = pix_dados.get("encodedImage", "")

                img_qr = ft.Image(src=f"data:image/png;base64,{qr_base64}", width=180, height=180) if qr_base64 else ft.Icon(ft.Icons.QR_CODE_2, size=140)

                async def fechar_modal_pix(e):
                    bs.open = False
                    await page.update_async() if hasattr(page, 'update_async') else page.update()

                bs = ft.BottomSheet(
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Text("⚡ Pagamento via PIX", size=18, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL),
                            ft.Text(f"Valor: R$ {valor:.2f}", size=14, weight=ft.FontWeight.W_500),
                            img_qr,
                            ft.ElevatedButton(
                                "📋 Copiar Chave PIX Copia e Cola", 
                                icon=ft.Icons.COPY, 
                                on_click=lambda e: copiar_texto(payload_pix, "Chave PIX Copiada!")
                            ),
                            ft.TextButton("Fechar", on_click=fechar_modal_pix)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
                    )
                )
                page.open(bs)
                await page.update_async() if hasattr(page, 'update_async') else page.update()
            else:
                await exibir_snackbar("Não foi possível gerar o PIX para esta fatura no momento.")

        if faturas_asaas:
            for fatura in faturas_asaas:
                fatura_id = fatura.get("id")
                data_venc = fatura.get("dueDate", "S/D")
                if "-" in data_venc:
                    p = data_venc.split("-")
                    data_venc = f"{p[2]}/{p[1]}/{p[0]}"
                valor = fatura.get("value", 0.0)
                status = str(fatura.get("status", "PENDING")).upper()

                status_texto, cor_status, is_pago = "Pendente", ft.Colors.ORANGE, False
                if status in ["RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"]:
                    status_texto, cor_status, is_pago = "Pago", ft.Colors.GREEN
                    is_pago = True
                elif status in ["OVERDUE", "DUNNING_REQUESTED"]:
                    status_texto, cor_status = "Vencido", ft.Colors.RED

                botoes_acao = [
                    ft.ElevatedButton("⚡ Pagar via PIX", style=ft.ButtonStyle(bgcolor=COR_PRINCIPAL, color="white"), on_click=lambda e, fid=fatura_id, val=valor: abrir_modal_pix(fid, val)),
                    ft.IconButton(ft.Icons.COPY_ALL, icon_color=COR_PRINCIPAL, on_click=lambda e, fid=fatura_id: copiar_texto(fid, "ID copiado!"))
                ] if not is_pago else [
                    ft.Icon(ft.Icons.CHECK_CIRCLE, color="green", size=18), 
                    ft.Text("Pagamento confirmado", size=11, color="grey600")
                ]

                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"Vencimento: {data_venc}", weight=ft.FontWeight.BOLD, size=14), 
                            ft.Container(content=ft.Text(status_texto, color="white", size=10, weight=ft.FontWeight.BOLD), bgcolor=cor_status, padding=5, border_radius=5)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(f"Valor: R$ {valor:.2f}", size=15, color="grey800"),
                        ft.Divider(height=10, color="grey300"),
                        ft.Row(botoes_acao)
                    ]), border_radius=12, padding=15, border=ft.Border.all(width=1, color="#E2E8F0"), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    shadow=ft.BoxShadow(blur_radius=5, color="grey200", offset=ft.Offset(0, 3))
                )
                lista_cards.append(card)
        else:
            lista_cards.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.SEARCH_OFF, size=40, color="grey400"),
                        ft.Text("Nenhuma fatura encontrada no Asaas para este cliente.", size=13, color="grey700", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                        ft.Text("Verifique se o cliente possui cobranças ativas na Sandbox do Asaas.", size=11, color="grey500", text_align=ft.TextAlign.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20
                )
            )

        coluna_boletos = ft.ListView(controls=lista_cards, expand=1, spacing=15, padding=5)
        
        conteudo = ft.Container(
            content=ft.Column([
                ft.Text("💵 Meus Boletos & PIX", size=24, weight=ft.FontWeight.BOLD, color=COR_PRINCIPAL), 
                ft.Container(content=coluna_boletos, width=340, height=450), 
                ft.TextButton("Voltar", icon=ft.Icons.ARROW_BACK, on_click=mostrar_menu_inicial)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            width=390, height=740, bgcolor=ft.Colors.SURFACE, shadow=ft.BoxShadow(blur_radius=20, color="grey300", offset=ft.Offset(0, 8)), border_radius=16
        )
        await mudar_tela(conteudo)

    # --- INICIALIZAÇÃO DA APLICAÇÃO ---
    if os.path.exists(ARQUIVO_SESSAO):
        os.remove(ARQUIVO_SESSAO)
    
    await mostrar_tela_login()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ft.app(
        target=main,
        assets_dir=PASTA_PDFS,
        host="0.0.0.0",
        port=port
    )