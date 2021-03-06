'''
Fichier de routage depuis lequel on accède aux différentes pages du site
'''

from flask import render_template, redirect, url_for, flash, request, g
from app.api import Api
from app import app, db
from app.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm, SearchForm
from app.mail import send_password_reset_email
from flask_login import current_user, login_user
from app.models import User
from flask_login import logout_user
from flask_login import login_required
from werkzeug.urls import url_parse
from datetime import datetime

tv_genres = Api.get_genre('tv')
movie_genres = Api.get_genre('movie')
logo_nom_source = "../static/assets/LogoNom.png"
logo_source = "../static/assets/Logo.png"


@app.route('/')
@app.route('/home')
@login_required
def home():
    """
    Cette fonction permet de retourner la home page de notre site qui indique les dernieres sorties de
    series et films. On passe egalement les genres de series et de films en parametres pour la sidebar
    :return:void
    """
    suggestions_serie = Api.get_popular('serie', 1)
    suggestions_movie = Api.get_popular('movie', 1)
    selection_serie, selection_movie = [], []
    for i in range(12):
        selection_serie.append(suggestions_serie[i])
        selection_movie.append(suggestions_movie[i])
    return render_template('home.html', title='Home', suggestions_serie=selection_serie,
                           suggestions_movie=selection_movie, nombre_series=12,
                           tv_genres=tv_genres, movie_genres=movie_genres)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Cette route correspond a la page de login
    On verifie que l'utilisateur a bien rentré les bonnes informations de connexion sinon on refuse son authentification
    Puis, si les informations sont bonnes, on recalcule l'etat des series de l'utilisateur (utd, nutd et fin) pour
        pouvoir afficher les bonnes notifications (que l'on rend donc actives)
    De plus, on lui cree un nouvel identifiant de session pour pouvoir poster sur l'API
    Enfin, on le redirige vers la page qu'il souhaitait voir (home si il n'en a pas)
    :return:
    """

    app.logger.info(msg='The user is logging in')

    # Si l'utilisateur est deja connecte, il ne peut acceder a cette page
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    # On utilise LoginForm du module forms.py
    form = LoginForm()

    # Si le formulaire n'est pas rempli, on demande de le reremplir
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        # Si aucun utilisateur n'a ce nom on flash un message indiquant qu'il y a eu une erreur dans le nom
        if user is None:
            app.logger.info(msg='Invalid Username !')
            flash("Invalid Username !")
            return render_template('login.html', title='Sign In', form=form, src=logo_source)

        # Si le mot de passe n'est pas bon, on l'indique egalement a l'utilisateur
        elif not user.check_password(form.password.data):
            app.logger.info(msg='Invalid Password !')
            flash("Invalid Password !")
            return render_template('login.html', title='Sign In', form=form, src=logo_source)

        # Sinon, on connecte l'utilisateur et on met a jour ses informations
        else:
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            app.logger.info(msg='Successful Login !')

            # Si il n'a pas de pages en memoire, on le redirige vers home
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('home')

            # On lui ajoute une session
            current_user.session_id = Api.new_session()
            db.session.commit()

            # On rend ses notifications actives et on met a jour le statut de ses series
            current_user.notifications = bytes(1)
            current_user.update_all_upcoming_episodes()
            db.session.commit()
            return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form, src=logo_source)


@app.route('/logout')
def logout():

    """
    Fonction appelee pour deconnecter l'utilisateur de sa session et revenir a la page de connexion
    :return:
    """
    logout_user()
    app.logger.info(msg='Successful Logout !')
    return redirect(url_for('login'))


@app.route('/media/<type_media>/<id>')
@login_required
def media(type_media, id):
    '''
    Route pour accéder à la page des détails d'un média (série ou film)
    :param type_media: string. Type du média : 'tv' ou 'movie'
    :param id: int. Id du média
    :return:
    '''
    media = Api.get_media(type_media=type_media, id_media=id)
    similar = Api.get_similar(id=id, media_type=type_media)
    if media is None:
        app.logger.info(msg=f'Incorrect {type_media} id')
        return render_template('404.html')
    else:
        app.logger.info(msg=f'Successful query for the {type_media} id={media.id} page')
        if type_media == 'tv':
            if current_user.is_in_medias(id_media=id, type_media=type_media):
                media.selected_episode = current_user.get_last_episode_viewed(id)
            episode = media.get_episode
            return render_template('serie.html', media=media, episode=episode, user=current_user, type_media=type_media,
                                   tv_genres=tv_genres, movie_genres=movie_genres, similar=similar)
        else:
            return render_template('movie.html', media=media, user=current_user, type_media=type_media,
                                   tv_genres=tv_genres, movie_genres=movie_genres, similar=similar)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Cette route permet a l'utilisateur de s'inscrire sur le site
    Il ne peut pas y acceder si il est deja connecte
    :return:
    """

    # On verifie que l'utilisateur n'est pas connecte
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    # On utilise le formulaire RegistrationForm du module form.py
    form = RegistrationForm()

    # Si le formulaire est valide (les champs sont remplis uniques et coherents) on redirige l'utilisateur vers
    # la page de connexion
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, name=form.name.data, surname=form.surname.data,
                    password=form.password.data)
        db.session.add(user)
        db.session.commit()
        app.logger.info(msg='Successful registry')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form, src=logo_source)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    '''
    Cette route affiche un formulaire pour que l'utilisateur demande un changement de mot de passe
    :return:
    '''
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
            flash('Check your email for the instructions to reset your password')
            return redirect(url_for('request_confirmed'))
        else:
            form.email.errors.append("No user has this email adress")
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form, src=logo_nom_source)


@app.route('/request_confirmed')
def request_confirmed():
    '''
    Cette route correspond à la page de confirmation après avoir fait une demande de changement de mot de passe
    :return:
    '''
    return render_template('request_confirmed.html', title='Request confirmed', src=logo_nom_source)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    '''
    Cette route est accedé depuis le mail envoyé après une demande de changement de mot de passe
    Elle permet à l'utilisateur de choisir un nouveau mot de passe
    :param token: string, le token envoyé par mail
    :return:
    '''
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.route('/add/<type_media>/<id_media>')
@login_required
def add(id_media, type_media):
    """
    Fonction appelee pour ajouter un film ou une serie a la liste de l'utilisateur
    :param id_media: int. Id du média
    :param type_media: string. Type du média : 'tv' ou 'movie'
    :return:void
    """
    current_user.add_media(id_media=id_media, type_media=type_media)
    app.logger.info(msg=f'Media {type_media} {id_media} successfully added')
    return media(type_media=type_media, id=id_media)


@app.route('/remove/<type_media>/<id_media>')
@login_required
def remove(id_media, type_media):
    """
    Fonction appelee pour retirer un film ou une serie de la liste de l'utilisateur
    :param id_media: int. Id du média
    :param type_media: string. Type du média : 'tv' ou 'movie'
    :return:void
    """
    current_user.remove_media(id_media=id_media, type_media=type_media)
    app.logger.info(msg=f'{type_media} {id_media} successfully removed')
    return media(type_media=type_media, id=id_media)


@app.route('/mymedias/<type_media>')
@login_required
def my_media(type_media):
    """
    Fonction appelee pour avoir la page correspondant a la liste des films ou des series ajoutes par l'utilisateur
    :param type_media: string. Type du média : 'tv' ou 'movie'
    :return: void
    """
    list_medias = current_user.list_media(media=type_media)
    list_medias_rendered =[]
    nb_medias = 0
    if not list_medias:
        app.logger.info(msg=f"My{type_media}s page rendered without {type_media}s")
    else:
        for m in list_medias:
            nb_medias += 1
            media = Api.get_media(type_media=type_media, id_media=m)
            list_medias_rendered.append(media)
        app.logger.info(msg=f'My{type_media}s page rendered')
        app.logger.info(msg=f'The {type_media} list has {nb_medias} {type_media}s')
    return render_template('myMedias.html', title=f'My{type_media}', type_media=type_media,
                           list_medias=list_medias_rendered, nb_medias=nb_medias, tv_genres=tv_genres,
                           movie_genres=movie_genres, user=current_user)


@app.route('/search2/<string>/<page>')
@login_required
def search2(string, page):
    """
    Fonction appelee pour la recherche de films et series correspondant a "string", permet d'aller a la page de resultats
    de recherche
    :param string: string. Recherche effectuée par l'utilisateur
    :param page: int. Numéro de la page des résultats
    :return:
    """
    list_series, list_movies, nb_pages = Api.search(string, page)
    app.logger.info(msg=f'Search page {page} rendered for : {string}')
    return render_template('search.html', title='Search', list_series=list_series, tv_genres=tv_genres,
                           movie_genres=movie_genres,
                           list_movies=list_movies, nb_pages=nb_pages, current_page=int(page), search=string)


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = 'en'


@app.route('/search')
@login_required
def search():
    """
    Redirection vers la fonction search2
    :return:
    """
    return redirect(f'/search2/{g.search_form.s.data}/1')


@app.route('/genre/<media>/<genre>/<page>')
@login_required
def genre(media, genre, page):
    """
    Cette route permet d'accéder à la page qui recense tous les médias d'un certain genre
    :param media: string. Type de média : 'tv' ou 'movie'
    :param genre: string. Nom du genre
    :param page: int. Numéro de la page des résultats
    :return:
    """
    if media == 'movie':
        list_genres = movie_genres
    else :
        list_genres = tv_genres
    for i in range(len(list_genres)):
        if list_genres[i]['name'] == genre:
            index_genre = i
    id_genre = list_genres[index_genre]['id']
    list_media, nb_pages = Api.discover(media, id_genre, page)
    app.logger.info(msg=f'Genre request on : Genre = {genre}, Media = {media}, Page = {page}')
    return render_template('genre.html', genre=genre, list_medias=list_media, media=media,
                           tv_genres=tv_genres, movie_genres=movie_genres, current_page=int(page), nb_pages=nb_pages)


@app.route('/media/tv/<id>/season/<season>/episode/<episode>')
@login_required
def select_episode(id, season, episode):
    """
    Fonction utilisee pour afficher l'episode {episode} de la saison {season} dans la page serie : son image et son
    resume
    :param id: int. id de la série
    :param season: numéro de la saison
    :param episode: numéro de l'épisode
    :return:
    """
    serie = Api.get_media(type_media='tv', id_media=id)
    similar = Api.get_similar(id, 'tv')
    serie.selected_episode = 'S' + str(season) + 'E' + str(episode)
    episode = serie.get_episode
    app.logger.info(msg=f'Selected Episode : Serie = {id}, Season = {season}, episode = {episode.num_episode}')
    return render_template('serie.html', media=serie, user=current_user, episode=episode, season=episode.num_season,
                           type_media='tv', similar=similar, tv_genres=tv_genres, movie_genres=movie_genres)


@app.route('/media/tv/<id>/season/<season>/episode/<episode>/view')
@login_required
def next_episode(id, season, episode):
    """
    Fonction appelee pour marquer un episode d'une serie comme vu
    :param id: int. id de la série
    :param season: numéro de la saison
    :param episode: numéro de l'épisode
    :return:
    """
    current_user.view_episode(episode, season, id)
    app.logger.info(msg=f'The user marked S{season}E{episode} from serie {id} as viewed')
    return media(type_media='tv', id=id)


@app.route('/rate/<i>')
@login_required
def rate(i):
    """
    Fonction appelee pour mettre a jour la note actuelle de l'utilisateur qui sera celle envoyee
    avec la fonction suivante
    :param i: note
    :return:
    """
    g = float(2*int(i))
    current_user.update_grade(g)
    app.logger.info(msg=f'The user is selecting the grade {float(2 * int(i))}')
    return '', 204


@app.route('/post/grade/<type_media>/<id_media>')
@login_required
def post_media_grade(id_media, type_media):
    """
    Fonction appelee pour envoyer a l'API la note donnee par l'utilisateur au film ou a la serie

    :param id_media: int. Id du média
    :param type_media: string. Type du média : 'tv' ou 'movie"
    :return:
    """
    grade = current_user.current_grade
    session = current_user.session_id
    current_user.grade(id_media=id_media, media=type_media, grade=grade)
    Api.rate(id=id_media, grade=grade, media=type_media, session=session, user=current_user)
    app.logger.info(msg=f'The user posted the grade {int(grade)} for the {type_media} {id_media}')
    return media(type_media=type_media, id=id_media)


@app.route('/unrate/<type_media>/<id_media>')
@login_required
def unrate_media(id_media, type_media):
    """
    Fonction appelee pour enlever la note donnee par l'utilsateur a une serie ou un film
    
    :param id_media: int. Id du média
    :param type_media: string. Type du média : 'tv' ou 'movie"
    :return:
    """
    current_user.unrate(type=type_media, id=id_media)
    app.logger.info(msg=f'The user unrated the {type_media} {id_media}')
    return media(type_media=type_media, id=id_media)


@app.route('/topRated/<media>/<page>')
@login_required
def topRated(media, page):
    """
    This function is called when the user tries to access the popular pannel from one of the pages
    We start by getting the API result with the API class
    :param media:String (movie or tv)
    :param page:int (>0)
    :return:void
    """
    # we get the result from the API
    top_rated_medias, nb_pages = Api.get_top_rated(media, page)
    app.logger.info(msg=f'Top Rated request on Media = {media}, Page = {page}')
    return render_template('topRatedMedias.html', list_medias=top_rated_medias, current_page=int(page),
                           media=media, page=page, nb_pages=nb_pages, tv_genres=tv_genres, movie_genres=movie_genres)


@app.route('/upcoming')
@login_required
def upcomingEpisodes():
    """
    This function is called when the user is trying to go on his upcoming episode page
    We provide the different series lists divided in 3 :
        * The series the user is watching but is not up to date (ex : the user last saw the episode 3 of the first season
            while the series last episode is S4E3 > list_series_last_episode
        * The user is up to date with this serie and we're expecting an episode for this show > list_series_up_to_date
        * The user is up-to-date with the serie but we're not expecting any next episode > list_series_finished
    We also change the notifications to 0
    :return:render_template('upcoming_episode.html')
    """
    l_utd, l_nutd, l_fin = current_user.check_upcoming_episodes()

    # We fill the list with all the series info using the Api get_serie method
    list_up_to_date, list_not_up_to_date, list_finished = [], [], []
    for s_id in l_utd:
        app.logger.info(msg=f'Serie {s_id} added to up to date shows')
        list_up_to_date.append(Api.get_media(type_media='tv', id_media=s_id))

    for s_id in l_nutd:
        app.logger.info(msg=f'Serie {s_id} added to not up to date shows')
        list_not_up_to_date.append(Api.get_media(type_media='tv', id_media=s_id))

    for s_id in l_fin:
        app.logger.info(msg=f'Serie {s_id} added to finished shows')
        list_finished.append(Api.get_media(type_media='tv', id_media=s_id))

    current_user.notifications = bytes(0)
    db.session.commit()

    return render_template('upcoming_episodes.html', title='Upcoming Episodes', list_next_episode=list_up_to_date,
                           list_last_episode=list_not_up_to_date, list_finished=list_finished,
                           tv_genres=tv_genres, movie_genres=movie_genres, user=current_user)
