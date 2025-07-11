# sistema_pontuacao_flask.py

from flask import Flask, render_template, request, redirect, jsonify
from flask import flash, redirect, url_for
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'confie'


# =======================================================================
# BANCO DE DADOS
# =======================================================================
def init_db():
    if not os.path.exists('pontos.db'):
        conn = sqlite3.connect('pontos.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS pontuacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                setor TEXT,
                obrigacao TEXT,
                pontuacao TEXT,
                observacao TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS loja (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        conn.commit()
        conn.close()

# =======================================================================
# OBRIGAÇÕES POR SETOR
# =======================================================================
OBRIGACOES = {
    'Logistica': [
        ('Entregas concluidas 100%', '(+)1 ponto/dia'),
        ('Veiculo limpo e organizado', '(+)1 ponto/dia'),
        ('Acerto organizado e correto', '(+)1 ponto/dia'),
        ('Questões de jornada (atrasos, ponto, etc)', '(-)2 pontos/dia'),
        ('Erro do entregador', '(-)1 ponto/dia')
    ],
    'Comercial': [
        ('Meta diária batida/conversão 70%', '(+)2 ponto/dia'),
        ('Cliente novo/Prospecção', '(+)1 ponto/dia'),
        ('Erro de pedido ou cliente insatisfeito', '(-)1 ponto/dia'),
        ('Inadimplência', '(-)1 ponto/dia')
    ]
}

# =======================================================================
# ROTAS PADRÕES
# =======================================================================
# Registrar filtro para formatar data
@app.template_filter('datetimeformat')
def datetimeformat(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return value


@app.route('/')
def home():
    conn = sqlite3.connect('pontos.db')
    cur = conn.cursor()

    setores = []

    # Loja (sem média)
    cur.execute("SELECT total FROM loja")
    loja_pontos = [row[0] for row in cur.fetchall()]
    setores.append({
        'nome': 'Loja',
        'total_registros': len(loja_pontos),
        'soma': sum(loja_pontos),
        'media': None,
        'valor_grafico': sum(loja_pontos)
    })

    # Expedição (sem média)
    cur.execute("SELECT total FROM expedicao")
    expedicao_pontos = [row[0] for row in cur.fetchall()]
    setores.append({
        'nome': 'Expedição',
        'total_registros': len(expedicao_pontos),
        'soma': sum(expedicao_pontos),
        'media': None,
        'valor_grafico': sum(expedicao_pontos)
    })

    # Logística (usa média)
    cur.execute("SELECT total FROM logistica")
    logistica_pontos = [row[0] for row in cur.fetchall()]
    media_log = round(sum(logistica_pontos) / 6, 2) if logistica_pontos else 0  # 6 motoristas
    setores.append({
        'nome': 'Logística',
        'total_registros': len(logistica_pontos),
        'soma': sum(logistica_pontos),
        'media': media_log,
        'valor_grafico': media_log
    })

    # Comercial (usa média)
    cur.execute("SELECT total FROM comercial")
    comercial_pontos = [row[0] for row in cur.fetchall()]
    media_com = round(sum(comercial_pontos) / 8, 2) if comercial_pontos else 0  # 8 vendedores
    setores.append({
        'nome': 'Comercial',
        'total_registros': len(comercial_pontos),
        'soma': sum(comercial_pontos),
        'media': media_com,
        'valor_grafico': media_com
    })

    cur.close()
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

    conn = sqlite3.connect('pontos.db')
    c = conn.cursor()
    c.execute('INSERT INTO pontuacoes (data, setor, obrigacao, pontuacao, observacao) VALUES (?, ?, ?, ?, ?)',
              (data, setor, obrigacao, pontuacao, observacao))
    conn.commit()
    conn.close()

    flash("✅ Pontuação registrada com sucesso!", "success")
    return redirect('/')

@app.route('/historico')
def historico():
    conn = sqlite3.connect('pontos.db')
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

        total = A + B + C - D - (2 * E) + extras_pontos

        conn = sqlite3.connect('pontos.db')
        c = conn.cursor()
        c.execute("INSERT INTO loja (data, A, B, C, D, E, extras, observacao, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (data, A, B, C, D, E, ','.join(extras), observacao, total))
        conn.commit()
        conn.close()
        flash("✅ Pontuação registrada com sucesso!", "success")
        return redirect('/loja')

    return render_template('loja.html')

@app.route('/historico_loja')
def historico_loja():
    conn = sqlite3.connect('pontos.db')
    c = conn.cursor()
    c.execute('SELECT data, A, B, C, D, E, extras, observacao, total FROM loja ORDER BY data DESC')
    registros = c.fetchall()
    conn.close()
    return render_template('historico_loja.html', registros=registros)

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

        total = A + B + C - D - E + extras_pontos

        conn = sqlite3.connect('pontos.db')
        c = conn.cursor()
        c.execute("INSERT INTO expedicao (data, A, B, C, D, E, extras, observacao, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (data, A, B, C, D, E, ','.join(extras), observacao, total))
        conn.commit()
        conn.close()

        flash("✅ Pontuação registrada com sucesso!", "success")
        return redirect('/expedicao')

    return render_template('expedicao.html')

@app.route('/historico_expedicao')
def historico_expedicao():
    conn = sqlite3.connect('pontos.db')
    c = conn.cursor()
    c.execute('SELECT data, A, B, C, D, E, extras, observacao, total FROM expedicao ORDER BY data DESC')
    registros = c.fetchall()
    conn.close()
    return render_template('historico_expedicao.html', registros=registros)

# Nova rota para a Logística com menu de motoristas e formulário de pontuação
@app.route('/logistica', methods=['GET', 'POST'])
def logistica():
    conn = sqlite3.connect('pontos.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS logistica (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    motoristas = ['Denilson', 'Fabio', 'Renan', 'Robson', 'Simone', 'Vinicius']

    if request.method == 'POST':
        data = request.form['data']
        motorista = request.form['motorista']
        A = int(request.form.get('A', 0))
        B = int(request.form.get('B', 0))
        C = int(request.form.get('C', 0))
        D = int(request.form.get('D', 0))
        E = int(request.form.get('E', 0))
        extras = request.form.getlist('extras')
        observacao = request.form.get('observacao', '')

        total = A + B + C - D - (2 * E)
        if 'meta' in extras:
            total += 2
        if 'equipe90' in extras:
            total += 1

        c.execute('INSERT INTO logistica (data, motorista, A, B, C, D, E, extras, observacao, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                  (data, motorista, A, B, C, D, E, ','.join(extras), observacao, total))
        conn.commit()
        flash("✅ Pontuação da logística registrada com sucesso!", "success")
        return redirect('/logistica')

    conn.close()
    return render_template('logistica.html', motoristas=motoristas)

@app.route('/historico_logistica')
def historico_logistica():
    motorista = request.args.get('motorista', '')
    conn = sqlite3.connect('pontos.db')
    c = conn.cursor()
    motoristas = ['Denilson', 'Fabio', 'Renan', 'Robson', 'Simone', 'Vinicius']
    
    if motorista:
        c.execute('SELECT data, motorista, A, B, C, D, E, extras, observacao, total FROM logistica WHERE motorista = ? ORDER BY data DESC', (motorista,))
    else:
        c.execute('SELECT data, motorista, A, B, C, D, E, extras, observacao, total FROM logistica ORDER BY data DESC')
    
    registros = c.fetchall()
    conn.close()

    total_geral = sum(int(r[9]) for r in registros)
    
    # Se um motorista estiver filtrado, a média é só dele
    if motorista:
        media = total_geral
    else:
        media = total_geral / len(motoristas) if motoristas else 0

    return render_template('historico_logistica.html', registros=registros, motorista=motorista, motoristas=motoristas, total_geral=total_geral, media=media)


# =======================================================================
# COMERCIAL
# =======================================================================
@app.route('/comercial', methods=['GET', 'POST'])
def comercial():
    conn = sqlite3.connect('pontos.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS comercial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    vendedores = ['EVERTON', 'MARCELO', 'PEDRO', 'SILVANA', 'TIAGO', 'RODOLFO', 'MARCOS', 'THYAGO']

    if request.method == 'POST':
        data = request.form['data']
        vendedor = request.form['vendedor']
        A = int(request.form.get('A', 0))
        B = int(request.form.get('B', 0))
        C = int(request.form.get('C', 0))
        D = int(request.form.get('D', 0))
        E = int(request.form.get('E', 0))
        extras = request.form.getlist('extras')
        observacao = request.form.get('observacao', '')

        total = (A * 2) + B + C - D - E
        if 'meta' in extras:
            total += 2
        if 'equipe90' in extras:
            total += 1

        c.execute('''
            INSERT INTO comercial (data, vendedor, A, B, C, D, E, extras, observacao, total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data, vendedor, A, B, C, D, E, ','.join(extras), observacao, total))

        conn.commit()
        conn.close()

        flash("✅ Pontuação registrada com sucesso!", "success")
        return redirect('/comercial')

    conn.close()
    return render_template('comercial.html', vendedores=vendedores)


@app.route('/historico_comercial')
def historico_comercial():
    vendedor = request.args.get('vendedor')
    conn = sqlite3.connect('pontos.db')
    cur = conn.cursor()

    if vendedor:
        cur.execute("SELECT * FROM comercial WHERE vendedor = ? ORDER BY data DESC", (vendedor,))
    else:
        cur.execute("SELECT * FROM comercial ORDER BY data DESC")
    registros = cur.fetchall()

    # 🔒 Lista fixa para o filtro, igual do formulário
    vendedores = ['EVERTON', 'MARCELO', 'PEDRO', 'SILVANA', 'TIAGO', 'RODOLFO', 'MARCOS', 'THYAGO']

    # Soma total e média
    total_geral = sum(int(r[10]) for r in registros)
    vendedores_unicos = list({r[2] for r in registros})  # r[2] = vendedor
    media = round(total_geral / len(vendedores_unicos), 2) if vendedores_unicos else 0

    cur.close()
    conn.close()

    return render_template('historico_comercial.html',
                           registros=registros,
                           vendedor=vendedor,
                           vendedores=vendedores,
                           total_geral=total_geral,
                           media=media)

@app.route('/zerar_tudo', methods=['POST'])
def zerar_tudo():
    senha = request.form.get('senha')
    if senha == "confie123":  # ajuste para sua senha desejada
        conn = sqlite3.connect('pontos.db')
        c = conn.cursor()
        for tabela in ['loja', 'expedicao', 'logistica', 'comercial']:
            c.execute(f"DELETE FROM {tabela}")
        conn.commit()
        conn.close()
        flash("✅ Todas as pontuações foram zeradas com sucesso!", "success")
    else:
        flash("❌ Senha incorreta. Ação cancelada.", "danger")
    return redirect('/')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)