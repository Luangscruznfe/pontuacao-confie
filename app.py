# sistema_pontuacao_flask.py

from flask import Flask, render_template, request, redirect, flash, url_for
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
import os
import cloudinary
import cloudinary.uploader
import tempfile
import zipfile
import pandas as pd


app = Flask(__name__)
app.secret_key = 'confie'

# Conexão com o banco PostgreSQL no Render
def get_db_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])

# Inicializa o banco e cria as tabelas se não existirem
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS pontuacoes (
            id SERIAL PRIMARY KEY,
            data TEXT,
            setor TEXT,
            obrigacao TEXT,
            pontuacao TEXT,
            observacao TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS loja (
            id SERIAL PRIMARY KEY,
            data TEXT,
            A INTEGER,
            B INTEGER,
            C INTEGER,
            D INTEGER,
            E INTEGER,
            extras TEXT,
            observacao TEXT,
            total INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS expedicao (
            id SERIAL PRIMARY KEY,
            data TEXT,
            A INTEGER,
            B INTEGER,
            C INTEGER,
            D INTEGER,
            E INTEGER,
            extras TEXT,
            observacao TEXT,
            total INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS logistica (
            id SERIAL PRIMARY KEY,
            data TEXT,
            motorista TEXT,
            A INTEGER,
            B INTEGER,
            C INTEGER,
            D INTEGER,
            E INTEGER,
            extras TEXT,
            observacao TEXT,
            total INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS comercial (
            id SERIAL PRIMARY KEY,
            data TEXT,
            vendedor TEXT,
            A INTEGER,
            B INTEGER,
            C INTEGER,
            D INTEGER,
            E INTEGER,
            extras TEXT,
            observacao TEXT,
            total INTEGER
        )
    ''')

    conn.commit()
    conn.close()

def fazer_backup_e_enviar():
    try:
        conn = get_db_connection()
        c = conn.cursor()

        tabelas = ['loja', 'expedicao', 'logistica', 'comercial', 'pontuacoes']
        arquivos_csv = []

        with tempfile.TemporaryDirectory() as tmpdirname:
            for tabela in tabelas:
                c.execute(f"SELECT * FROM {tabela}")
                rows = c.fetchall()
                colnames = [desc[0] for desc in c.description]

                if not rows:
                    continue

                # Salva CSV temporário
                df = pd.DataFrame(rows, columns=colnames)
                caminho_csv = os.path.join(tmpdirname, f"{tabela}.csv")
                df.to_csv(caminho_csv, index=False)
                arquivos_csv.append(caminho_csv)

            # Compactar todos os arquivos em um ZIP
            caminho_zip = os.path.join(tmpdirname, f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip")
            with zipfile.ZipFile(caminho_zip, 'w') as zipf:
                for file in arquivos_csv:
                    zipf.write(file, os.path.basename(file))

            # Enviar para o Cloudinary
            resultado = cloudinary.uploader.upload(
                caminho_zip,
                resource_type='raw',
                folder='backups_pontuacao',
                use_filename=True,
                unique_filename=False,
                overwrite=False
            )

            return resultado['secure_url']

    except Exception as e:
        print("Erro ao fazer backup automático:", e)
        return None



@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d/%m/%Y'):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime(format)
    except:
        return value

@app.route('/')
def home():
    conn = get_db_connection()
    c = conn.cursor()

    setores = []

    # Loja (sem média)
    c.execute("SELECT total FROM loja")
    loja_pontos = [row[0] for row in c.fetchall()]
    setores.append({
        'nome': 'Loja',
        'total_registros': len(loja_pontos),
        'soma': sum(loja_pontos) if loja_pontos else 0,
        'media': None,
        'valor_grafico': sum(loja_pontos) if loja_pontos else 0
    })

    # Expedição (sem média)
    c.execute("SELECT total FROM expedicao")
    expedicao_pontos = [row[0] for row in c.fetchall()]
    setores.append({
        'nome': 'Expedição',
        'total_registros': len(expedicao_pontos),
        'soma': sum(expedicao_pontos) if expedicao_pontos else 0,
        'media': None,
        'valor_grafico': sum(expedicao_pontos) if expedicao_pontos else 0
    })

    # Logística (usa média)
    c.execute("SELECT total FROM logistica")
    logistica_pontos = [row[0] for row in c.fetchall()]
    soma_log = sum(logistica_pontos) if logistica_pontos else 0
    media_log = round(soma_log / 6, 2) if soma_log else 0
    setores.append({
        'nome': 'Logística',
        'total_registros': len(logistica_pontos),
        'soma': soma_log,
        'media': media_log,
        'valor_grafico': media_log
    })

    # Comercial (usa média)
    c.execute("SELECT total FROM comercial")
    comercial_pontos = [row[0] for row in c.fetchall()]
    soma_com = sum(comercial_pontos) if comercial_pontos else 0
    media_com = round(soma_com / 8, 2) if soma_com else 0
    setores.append({
        'nome': 'Comercial',
        'total_registros': len(comercial_pontos),
        'soma': soma_com,
        'media': media_com,
        'valor_grafico': media_com
    })

    c.close()
    conn.close()

    return render_template(
        'home.html',
        total_loja=setores[0]['total_registros'],
        soma_loja=setores[0]['soma'],
        total_expedicao=setores[1]['total_registros'],
        soma_expedicao=setores[1]['soma'],
        total_logistica=setores[2]['total_registros'],
        soma_logistica=setores[2]['soma'],
        media_logistica=setores[2]['media'],
        total_comercial=setores[3]['total_registros'],
        soma_comercial=setores[3]['soma'],
        media_comercial=setores[3]['media']
    )


@app.route('/enviar', methods=['POST'])
def enviar():
    setor = request.form['setor']
    obrigacao = request.form['obrigacao']
    pontuacao = request.form['pontuacao']
    observacao = request.form.get('observacao', '')
    data = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    c = conn.cursor()

    c.execute('INSERT INTO pontuacoes (data, setor, obrigacao, pontuacao, observacao) VALUES (%s, %s, %s, %s, %s)',
              (data, setor, obrigacao, pontuacao, observacao))
    conn.commit()
    conn.close()

    flash("✅ Pontuação registrada com sucesso!", "success")
    return redirect('/')

@app.route('/historico')
def historico():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT data, setor, obrigacao, pontuacao, observacao FROM pontuacoes ORDER BY data DESC')
    registros = c.fetchall()
    conn.close()
    return render_template('historico.html', registros=registros)

# =======================================================================
# LOJA
# =======================================================================
# Função para converter valores de forma segura
def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

# Dentro da rota de envio (exemplo para Loja)
@app.route('/loja', methods=['GET', 'POST'])
def loja():
    if request.method == 'POST':
        data = request.form.get('data')
        A = safe_int(request.form.get('A'))
        B = safe_int(request.form.get('B'))
        C = safe_int(request.form.get('C'))
        D = safe_int(request.form.get('D'))
        E = safe_int(request.form.get('E'))
        observacao = request.form.get('observacao', '')
        extras = request.form.getlist('extras')

        # Pontos extras
        extras_pontos = 0
        if 'meta' in extras:
            extras_pontos += 2
        if 'equipe90' in extras:
            extras_pontos += 1

        total = A + B + C + D + E + extras_pontos

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO loja (data, A, B, C, D, E, extras, observacao, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                  (data, A, B, C, D, E, ','.join(extras), observacao, total))
        conn.commit()
        conn.close()
        flash("✅ Pontuação registrada com sucesso!", "success")
        fazer_backup_e_enviar()
        return redirect('/loja')

    
    return render_template('loja.html')

# =======================================================================
# EXPEDIÇÃO
# =======================================================================
@app.route('/expedicao', methods=['GET', 'POST'])
def expedicao():
    if request.method == 'POST':
        data = request.form.get('data')
        A = safe_int(request.form.get('A'))  # Organização e limpeza estoque
        B = safe_int(request.form.get('B'))  # Separação correta do mapa
        C = safe_int(request.form.get('C'))  # Faturamento OK
        D = safe_int(request.form.get('D'))  # Erros / Devoluções
        E = safe_int(request.form.get('E'))  # Finalização após horário (abaixo de 50k)
        extras = request.form.getlist('extras')
        observacao = request.form.get('observacao', '')

        # Pontos extras
        extras_pontos = 0
        if 'meta' in extras:
            extras_pontos += 2
        if 'equipe90' in extras:
            extras_pontos += 1

        total = A + B + C + D + E + extras_pontos

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO expedicao (data, A, B, C, D, E, extras, observacao, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                  (data, A, B, C, D, E, ','.join(extras), observacao, total))
        conn.commit()
        conn.close()

        flash("✅ Pontuação registrada com sucesso!", "success")
        fazer_backup_e_enviar()
        return redirect('/expedicao')

    return render_template('expedicao.html')

@app.route('/historico_expedicao')
def historico_expedicao():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT data, A, B, C, D, E, extras, observacao, total FROM expedicao ORDER BY data DESC')
    registros = c.fetchall()
    conn.close()

    total_geral = sum([r[8] for r in registros]) if registros else 0  # índice 8 = campo total

    return render_template('historico_expedicao.html', registros=registros, total_geral=total_geral)
	

# Nova rota para a Logística com menu de motoristas e formulário de pontuação
@app.route('/logistica', methods=['GET', 'POST'])
def logistica():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS logistica (
            id SERIAL PRIMARY KEY,
            data TEXT,
            motorista TEXT,
            A INTEGER,
            B INTEGER,
            C INTEGER,
            D INTEGER,
            E INTEGER,
            extras TEXT,
            observacao TEXT,
            total INTEGER
        )
    ''')

    motoristas = ['Denilson', 'Fabio', 'Renan', 'Robson', 'Simone', 'Vinicius', 'Equipe']

    if request.method == 'POST':
        data = request.form['data']
        motorista = request.form['motorista']
        A = safe_int(request.form.get('A'))
        B = safe_int(request.form.get('B'))
        C = safe_int(request.form.get('C'))
        D = safe_int(request.form.get('D'))
        E = safe_int(request.form.get('E'))
        extras = request.form.getlist('extras')
        observacao = request.form.get('observacao', '')

        total = A + B + C + D + E
        if 'meta' in extras:
            total += 2
        if 'equipe90' in extras:
            total += 1

        c.execute('''
            INSERT INTO logistica (data, motorista, A, B, C, D, E, extras, observacao, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (data, motorista, A, B, C, D, E, ','.join(extras), observacao, total))

        conn.commit()
        conn.close()
        flash("✅ Pontuação da logística registrada com sucesso!", "success")
        fazer_backup_e_enviar()
        return redirect('/logistica')

    conn.close()
    return render_template('logistica.html', motoristas=motoristas)


@app.route('/historico_logistica')
def historico_logistica():
    conn = get_db_connection()
    c = conn.cursor()

    motorista = request.args.get('motorista', '')
    motoristas = ['Denilson', 'Fabio', 'Renan', 'Robson', 'Simone', 'Vinicius', 'Equipe']

    if motorista:
        c.execute('''
            SELECT data, motorista, A, B, C, D, E, extras, observacao, total 
            FROM logistica 
            WHERE motorista = %s 
            ORDER BY data DESC
        ''', (motorista,))
    else:
        c.execute('''
            SELECT data, motorista, A, B, C, D, E, extras, observacao, total 
            FROM logistica 
            ORDER BY data DESC
        ''')

    registros = c.fetchall()
    conn.close()

    total_geral = sum([int(r[9]) for r in registros]) if registros else 0

    if motorista:
        media = Decimal(total_geral).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        motoristas_reais = [m for m in motoristas if m != 'Equipe']
        media = (
            Decimal(total_geral / len(motoristas_reais)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if motoristas_reais else Decimal('0.00')
        )

    return render_template(
        'historico_logistica.html',
        registros=registros,
        motorista=motorista,
        motoristas=motoristas,
        total_geral=total_geral,
        media=media
    )


@app.route('/historico_loja')
def historico_loja():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT data, A, B, C, D, E, extras, observacao, total FROM loja ORDER BY data DESC')
    registros = c.fetchall()
    conn.close()

    total_geral = sum([r[8] for r in registros]) if registros else 0  # índice 8 = campo 'total'
    media = round(total_geral / len(registros), 1) if registros else 0

    return render_template('historico_loja.html', registros=registros, total_geral=total_geral, media=media)

# =======================================================================
# COMERCIAL
# =======================================================================
@app.route('/comercial', methods=['GET', 'POST'])
def comercial():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS comercial (
        id SERIAL PRIMARY KEY,
            data TEXT,
            vendedor TEXT,
            A INTEGER,
            B INTEGER,
            C INTEGER,
            D INTEGER,
            E INTEGER,
            extras TEXT,
            observacao TEXT,
            total INTEGER
        )
    ''')

    # 🔒 Lista fixa de vendedores
    vendedores = ['EVERTON', 'MARCELO', 'PEDRO', 'SILVANA', 'TIAGO', 'RODOLFO', 'MARCOS', 'THYAGO', 'EQUIPE']

    if request.method == 'POST':
        data = request.form['data']
        vendedor = request.form['vendedor']
        A = safe_int(request.form.get('A'))
        B = safe_int(request.form.get('B'))
        C = safe_int(request.form.get('C'))
        D = safe_int(request.form.get('D'))
        E = safe_int(request.form.get('E'))
        extras = request.form.getlist('extras')
        observacao = request.form.get('observacao', '')

        total = A + B + C + D + E
        if 'meta' in extras:
            total += 2
        if 'equipe90' in extras:
            total += 1

        c.execute('''
            INSERT INTO comercial (data, vendedor, A, B, C, D, E, extras, observacao, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (data, vendedor, A, B, C, D, E, ','.join(extras), observacao, total))

        conn.commit()
        conn.close()

        flash("✅ Pontuação registrada com sucesso!", "success")
        fazer_backup_e_enviar()
        return redirect('/comercial')

    conn.close()
    return render_template('comercial.html', vendedores=vendedores)


@app.route('/historico_comercial')
def historico_comercial():
    conn = get_db_connection()
    c = conn.cursor()

    vendedor = request.args.get('vendedor', '')

    # Lista fixa de vendedores
    lista_vendedores = ['EVERTON', 'MARCELO', 'PEDRO', 'SILVANA', 'TIAGO', 'RODOLFO', 'MARCOS', 'THYAGO', 'EQUIPE']

    # Busca registros com ou sem filtro
    if vendedor:
        c.execute("SELECT * FROM comercial WHERE vendedor = %s ORDER BY data DESC", (vendedor,))
    else:
        c.execute("SELECT * FROM comercial ORDER BY data DESC")

    registros = c.fetchall()

    # Cálculo do total geral e média (com base no número de registros)
    total_geral = sum([r[10] for r in registros])  # campo total = índice 10
    media = Decimal(total_geral / 8).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    conn.close()

    return render_template(
        'historico_comercial.html',
        registros=registros,
        total_geral=total_geral,
        media=media,
        vendedores=lista_vendedores,
        vendedor=vendedor
    )


@app.route('/zerar_tudo', methods=['POST'])
def zerar_tudo():
    senha = request.form.get('senha')
    if senha == "confie123":  # ajuste para sua senha desejada
        conn = get_db_connection()
        c = conn.cursor()
        for tabela in ['loja', 'expedicao', 'logistica', 'comercial']:
            c.execute(f"DELETE FROM {tabela}")
        conn.commit()
        conn.close()
        flash("✅ Todas as pontuações foram zeradas com sucesso!", "success")
    else:
        flash("❌ Senha incorreta. Ação cancelada.", "danger")

    return redirect('/')


@app.route('/criar_banco')
def criar_banco():
    try:
        init_db()
        return "✅ Banco de dados criado com sucesso!"
    except Exception as e:
        return f"❌ Erro ao criar banco: {str(e)}"

@app.route('/restaurar_backup', methods=['GET', 'POST'])
def restaurar_backup():
    if request.method == 'POST':
        arquivo = request.files['backup']
        if arquivo and arquivo.filename.endswith('.zip'):
            try:
                with tempfile.TemporaryDirectory() as tmpdirname:
                    caminho_zip = os.path.join(tmpdirname, arquivo.filename)
                    arquivo.save(caminho_zip)

                    # Extrair ZIP
                    with zipfile.ZipFile(caminho_zip, 'r') as zip_ref:
                        zip_ref.extractall(tmpdirname)

                    # Conectar ao banco
                    conn = get_db_connection()
                    c = conn.cursor()

                    tabelas = ['loja', 'expedicao', 'logistica', 'comercial', 'pontuacoes']
                    for tabela in tabelas:
                        caminho_csv = os.path.join(tmpdirname, f"{tabela}.csv")
                        if os.path.exists(caminho_csv):
                            df = pd.read_csv(caminho_csv)

                            # Limpa a tabela
                            c.execute(f"DELETE FROM {tabela}")

                            # Insere os dados
                            for _, row in df.iterrows():
                                colunas = ','.join(df.columns)
                                valores = ','.join(['%s'] * len(df.columns))
                                c.execute(f"INSERT INTO {tabela} ({colunas}) VALUES ({valores})", tuple(row))

                    conn.commit()
                    conn.close()
                    flash("✅ Backup restaurado com sucesso!", "success")
                    return redirect('/')
            except Exception as e:
                flash(f"❌ Erro ao restaurar backup: {e}", "danger")
                return redirect('/restaurar_backup')

    return render_template('restaurar_backup.html')


if __name__ == '__main__':
        app.run(debug=True)