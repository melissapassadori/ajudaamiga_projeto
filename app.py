from flask import Flask, render_template, request, redirect, session
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = 'chave_secreta_tcc_senai'


def ligar_banco():
    banco = psycopg2.connect(
        host="localhost",
        database="tcc_moda",
        user="postgres",
        password="senai",
        port=5432
    )
    return banco


@app.route('/')
def inicio():
    return render_template('login.html')


@app.route('/cadastrar_usuario', methods=['POST'])
def cadastrar_usuario():
    nome = request.form['nome']
    email = request.form['email']
    senha = request.form['senha']

    banco = ligar_banco()
    cursor = banco.cursor()
    try:
        cursor.execute(
            'INSERT INTO usuario (nome, email, senha) VALUES (%s, %s, %s) RETURNING id_usuario',
            (nome, email, senha)
        )
        novo_id = cursor.fetchone()[0]
        banco.commit()

        session['usuario_id'] = novo_id
        session['usuario_nome'] = nome
        cursor.close()
        banco.close()
        return redirect('/boas_vindas')
    except Exception:
        banco.rollback()
        cursor.close()
        banco.close()
        return '''
            <script>
                alert("Este e-mail já está cadastrado!");
                window.location.href="/";
            </script>
        '''


@app.route('/fazer_login', methods=['POST'])
def fazer_login():
    email = request.form['email']
    senha = request.form['senha']

    banco = ligar_banco()
    cursor = banco.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM usuario WHERE email = %s AND senha = %s', (email, senha))
    usuario = cursor.fetchone()
    cursor.close()
    banco.close()

    if usuario:
        session['usuario_id'] = usuario['id_usuario']
        session['usuario_nome'] = usuario['nome']
        return redirect('/boas_vindas')
    else:
        return '''
            <script>
                alert("E-mail ou senha incorretos!");
                window.location.href="/";
            </script>
        '''


@app.route('/sair')
def sair():
    session.clear()
    return redirect('/')



@app.route('/boas_vindas')
def boas_vindas():
    if 'usuario_id' not in session:
        return redirect('/')
    return render_template('boas_vindas.html', nome=session['usuario_nome'])



@app.route('/quiz')
def quiz():
    if 'usuario_id' not in session:
        return redirect('/')
    return render_template('quiz.html', nome=session['usuario_nome'])


@app.route('/salvar_perfil', methods=['POST'])
def salvar_perfil():
    if 'usuario_id' not in session:
        return redirect('/')

    usuario_id = session['usuario_id']
    tom_pele = request.form['tom_pele']
    cor_cabelo = request.form['cor_cabelo']
    contraste = request.form['contraste']
    estilo_preferido = request.form['estilo_preferido']
    cartela_padrao = "Cartela Suave — Tons Pastel (Rosa, Lilás & Off-White)"

    banco = ligar_banco()
    cursor = banco.cursor()

    cursor.execute('DELETE FROM perfil_estilo WHERE usuario_id = %s', (usuario_id,))
    cursor.execute(
        '''
        INSERT INTO perfil_estilo (usuario_id, tom_pele, cor_cabelo, contraste, estilo_preferido, cartela_resultado)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        (usuario_id, tom_pele, cor_cabelo, contraste, estilo_preferido, cartela_padrao)
    )
    banco.commit()
    cursor.close()
    banco.close()

    return redirect('/resultado')


@app.route('/resultado')
def resultado():
    if 'usuario_id' not in session:
        return redirect('/')

    banco = ligar_banco()
    cursor = banco.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM perfil_estilo WHERE usuario_id = %s', (session['usuario_id'],))
    perfil = cursor.fetchone()
    cursor.close()
    banco.close()

    return render_template('resultado.html', perfil=perfil, nome=session['usuario_nome'])


@app.route('/loja')
def loja():
    if 'usuario_id' not in session:
        return redirect('/')

    categoria_atual = request.args.get('categoria', 'Todas')

    banco = ligar_banco()
    cursor = banco.cursor(cursor_factory=RealDictCursor)

    cursor.execute('SELECT * FROM perfil_estilo WHERE usuario_id = %s', (session['usuario_id'],))
    perfil = cursor.fetchone()

    if categoria_atual == 'Todas':
        cursor.execute('SELECT * FROM produto ORDER BY id_produto')
    else:
        cursor.execute('SELECT * FROM produto WHERE categoria = %s ORDER BY id_produto', (categoria_atual,))
    produtos = cursor.fetchall()

    cursor.execute('SELECT COALESCE(SUM(quantidade), 0) AS total FROM carrinho WHERE usuario_id = %s', (session['usuario_id'],))
    qtd_carrinho = cursor.fetchone()['total']

    cursor.close()
    banco.close()

    return render_template(
        'loja.html',
        produtos=produtos,
        perfil=perfil,
        nome=session['usuario_nome'],
        qtd_carrinho=qtd_carrinho,
        categoria_atual=categoria_atual
    )



@app.route('/produto/<id_produto>')
def detalhe_produto(id_produto):
    if 'usuario_id' not in session:
        return redirect('/')

    banco = ligar_banco()
    cursor = banco.cursor(cursor_factory=RealDictCursor)

    cursor.execute('SELECT * FROM produto WHERE id_produto = %s', (id_produto,))
    produto = cursor.fetchone()

    cursor.execute('SELECT COALESCE(SUM(quantidade), 0) AS total FROM carrinho WHERE usuario_id = %s', (session['usuario_id'],))
    qtd_carrinho = cursor.fetchone()['total']

    cursor.close()
    banco.close()

    return render_template('detalhe_produto.html', produto=produto, qtd_carrinho=qtd_carrinho)



@app.route('/adicionar_carrinho/<id_produto>')
def adicionar_carrinho(id_produto):
    if 'usuario_id' not in session:
        return redirect('/')

    usuario_id = session['usuario_id']
    banco = ligar_banco()
    cursor = banco.cursor(cursor_factory=RealDictCursor)

    cursor.execute('SELECT * FROM carrinho WHERE usuario_id = %s AND produto_id = %s', (usuario_id, id_produto))
    item = cursor.fetchone()

    if item:
        cursor.execute('UPDATE carrinho SET quantidade = quantidade + 1 WHERE id_carrinho = %s', (item['id_carrinho'],))
    else:
        cursor.execute('INSERT INTO carrinho (usuario_id, produto_id, quantidade) VALUES (%s, %s, 1)', (usuario_id, id_produto))

    banco.commit()
    cursor.close()
    banco.close()
    return redirect('/loja')


@app.route('/carrinho')
def ver_carrinho():
    if 'usuario_id' not in session:
        return redirect('/')

    banco = ligar_banco()
    cursor = banco.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        '''
        SELECT carrinho.id_carrinho, carrinho.quantidade,
               produto.nome, produto.preco, produto.imagem_url, produto.categoria,
               (carrinho.quantidade * produto.preco) AS subtotal
        FROM carrinho, produto
        WHERE carrinho.produto_id = produto.id_produto
        AND carrinho.usuario_id = %s
        ORDER BY carrinho.id_carrinho
        ''',
        (session['usuario_id'],)
    )
    itens = cursor.fetchall()
    total_geral = sum(item['subtotal'] for item in itens)

    cursor.close()
    banco.close()

    return render_template('carrinho.html', itens=itens, total_geral=total_geral, nome=session['usuario_nome'])


@app.route('/remover_carrinho/<id_carrinho>')
def remover_carrinho(id_carrinho):
    banco = ligar_banco()
    cursor = banco.cursor()
    cursor.execute('DELETE FROM carrinho WHERE id_carrinho = %s', (id_carrinho,))
    banco.commit()
    cursor.close()
    banco.close()
    return redirect('/carrinho')


@app.route('/finalizar_compra', methods=['POST'])
def finalizar_compra():
    if 'usuario_id' not in session:
        return redirect('/')

    banco = ligar_banco()
    cursor = banco.cursor()
    cursor.execute('DELETE FROM carrinho WHERE usuario_id = %s', (session['usuario_id'],))
    banco.commit()
    cursor.close()
    banco.close()

    return '''
        <script>
            alert("Pedido realizado com sucesso! Obrigada por comprar conosco.");
            window.location.href="/loja";
        </script>
    '''

@app.route('/contato')
def contato():
    if 'usuario_id' not in session:
        return redirect('/')
    return render_template('contato.html', nome=session['usuario_nome'])


@app.route('/enviar_feedback', methods=['POST'])
def enviar_feedback():
    if 'usuario_id' not in session:
        return redirect('/')

    nota = request.form['nota']
    mensagem = request.form['mensagem']

    banco = ligar_banco()
    cursor = banco.cursor()
    cursor.execute(
        'INSERT INTO feedback (usuario_id, nota, mensagem) VALUES (%s, %s, %s)',
        (session['usuario_id'], nota, mensagem)
    )
    banco.commit()
    cursor.close()
    banco.close()

    return '''
        <script>
            alert("Obrigada pelo seu feedback! Sua opinião é muito importante para nós.");
            window.location.href="/contato";
        </script>
    '''


if __name__ == '__main__':
    app.run()