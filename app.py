from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'mysecretkey'
db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db)

# ---------------------
# Models
# ---------------------

class BillingInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    postcode = db.Column(db.String(20))
    housenumber = db.Column(db.String(20))
    phone = db.Column(db.String(50))
    companyname = db.Column(db.String(100))
    email = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<BillingInfo {self.companyname or self.name}>'

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    telefoon = db.Column(db.String(50))
    referentie = db.Column(db.String(100))
    billing_info_id = db.Column(db.Integer, db.ForeignKey('billing_info.id'), nullable=True)
    vereniging = db.Column(db.String(200), nullable=True)  # Comma-separated string
    assignments = db.relationship('Assignment', backref='customer', cascade="all, delete-orphan", lazy=True)
    
    billing_info = db.relationship('BillingInfo', foreign_keys=[billing_info_id], uselist=False)

    def __repr__(self):
        return f'<Customer {self.name}>'

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Nieuw')
    status_opdracht = db.Column(db.String(255), nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    opmerkingen = db.Column(db.Text, nullable=True)
    file = db.Column(db.String(200))
    # Relatie naar dynamische items
    items = db.relationship('AssignmentItem', backref='assignment', cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f'<Assignment {self.title}>'

class AssignmentItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    item_type = db.Column(db.String(50), nullable=False)
    merk = db.Column(db.String(100))
    artikel_omschrijving = db.Column(db.String(200))
    file = db.Column(db.String(200))  # Voor de geüploade productafbeelding of bestand
    # Nieuwe velden:
    artikelnummer = db.Column(db.String(100))
    prijs = db.Column(db.String(50))
    kleur = db.Column(db.String(50))
    specs = db.Column(db.Text)  # JSON-string met specificatietabelgegevens

    def __repr__(self):
        return f'<AssignmentItem {self.item_type} - {self.artikel_omschrijving}>'

# ---------------------
# File upload settings
# ---------------------
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------------
# Routes
# ---------------------

@app.route('/')
def index():
    new_assignments = Assignment.query.filter_by(status='Nieuw').all()
    return render_template('index.html', new_assignments=new_assignments)

@app.route('/test')
def test():
    return "Test route werkt!"

# Klantenroutes

@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    error = None
    if request.method == 'POST':
        formdata = request.form
        name = formdata.get('name')
        email = formdata.get('email')
        telefoon = formdata.get('telefoon')
        referentie = formdata.get('referentie')
        selected_verenigingen = formdata.getlist('vereniging[]')
        andere_vereniging = formdata.get('andere_vereniging', '').strip()
        if andere_vereniging:
            selected_verenigingen.append(andere_vereniging)
        vereniging_str = ','.join(selected_verenigingen) if selected_verenigingen else None
        
        new_customer = Customer(
            name=name, 
            email=email, 
            telefoon=telefoon,
            vereniging=vereniging_str, 
            referentie=referentie
        )
        db.session.add(new_customer)
        db.session.commit()
        
        factuur_naam = formdata.get('factuur_naam')
        if factuur_naam:
            existing_bi = BillingInfo.query.filter_by(
                name=factuur_naam,
                companyname=formdata.get('factuur_companyname'),
                address=formdata.get('factuur_adres'),
                postcode=formdata.get('factuur_postcode'),
                housenumber=formdata.get('factuur_huisnummer'),
                phone=formdata.get('factuur_telefoon'),
                email=formdata.get('factuur_email')
            ).first()
            if existing_bi:
                new_customer.billing_info_id = existing_bi.id
            else:
                new_bi = BillingInfo(
                    name=factuur_naam,
                    companyname=formdata.get('factuur_companyname'),
                    address=formdata.get('factuur_adres'),
                    postcode=formdata.get('factuur_postcode'),
                    housenumber=formdata.get('factuur_huisnummer'),
                    phone=formdata.get('factuur_telefoon'),
                    email=formdata.get('factuur_email')
                )
                db.session.add(new_bi)
                db.session.commit()
                new_customer.billing_info_id = new_bi.id
            db.session.commit()
        
        flash('Klant en (indien ingevuld) factuurgegevens succesvol toegevoegd!', 'success')
        return redirect(url_for('list_customers'))
    
    billing_infos = BillingInfo.query.all()
    formdata = {}
    return render_template('add_customer.html', error=error, billing_infos=billing_infos, formdata=formdata)

@app.route('/customers')
def list_customers():
    customers = Customer.query.all()
    return render_template('customers.html', customers=customers)

@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    billing_info = customer.billing_info
    billing_infos = BillingInfo.query.all()
    
    if request.method == 'POST':
        formdata = request.form
        customer.name = formdata.get('name')
        customer.email = formdata.get('email')
        customer.telefoon = formdata.get('telefoon')
        customer.referentie = formdata.get('referentie')
        
        factuur_naam = formdata.get('factuur_naam')
        if factuur_naam:
            if billing_info:
                billing_info.name = factuur_naam
                billing_info.companyname = formdata.get('factuur_companyname')
                billing_info.address = formdata.get('factuur_adres')
                billing_info.postcode = formdata.get('factuur_postcode')
                billing_info.housenumber = formdata.get('factuur_huisnummer')
                billing_info.phone = formdata.get('factuur_telefoon')
                billing_info.email = formdata.get('factuur_email')
            else:
                new_bi = BillingInfo(
                    name=factuur_naam,
                    companyname=formdata.get('factuur_companyname'),
                    address=formdata.get('factuur_adres'),
                    postcode=formdata.get('factuur_postcode'),
                    housenumber=formdata.get('factuur_huisnummer'),
                    phone=formdata.get('factuur_telefoon'),
                    email=formdata.get('factuur_email')
                )
                db.session.add(new_bi)
                db.session.flush()
                customer.billing_info_id = new_bi.id
        else:
            customer.billing_info_id = None
        
        selected_verenigingen = formdata.getlist('vereniging[]')
        andere_vereniging = formdata.get('andere_vereniging', '').strip()
        if andere_vereniging:
            selected_verenigingen.append(andere_vereniging)
        customer.vereniging = ','.join(selected_verenigingen) if selected_verenigingen else None
        
        db.session.commit()
        flash('Klant succesvol bijgewerkt!', 'success')
        return redirect(url_for('list_customers'))
    
    known_verenigingen = {"Jonge Kracht", "RKHVV", "HCOB"}
    ven_list = []
    vrije_invoer = ""
    if customer.vereniging:
        items = customer.vereniging.split(',')
        for item in items:
            if item in known_verenigingen:
                ven_list.append(item)
            else:
                vrije_invoer = item
    return render_template('edit_customer.html',
                           customer=customer,
                           billing_info=billing_info,
                           billing_infos=billing_infos,
                           ven_list=ven_list,
                           vrije_invoer=vrije_invoer)

@app.route('/delete_customer/<int:id>', methods=['POST'])
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    flash('Klant succesvol verwijderd!', 'success')
    return redirect(url_for('list_customers'))

# ---------------------
# Opdrachtenroutes
# ---------------------

@app.route('/add_assignment', methods=['GET', 'POST'])
def add_assignment():
    error = None
    customers = Customer.query.all()
    if request.method == 'POST':
        # Basisvelden
        customer_id = request.form.get('customer_id')
        title = "Opdracht " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        description = ""
        
        deadline_str = request.form.get('deadline')
        if deadline_str:
            deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        else:
            deadline_dt = None
        
        opmerkingen = request.form.get('opmerkingen') or ""
        status_opdracht = request.form.get('status_opdracht') or ""
        
        file = request.files.get('file')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_assignment = Assignment(
            customer_id=customer_id,
            title=title,
            description=description,
            file=filename,
            status='Nieuw',
            status_opdracht=status_opdracht,
            deadline=deadline_dt,
            opmerkingen=opmerkingen
        )
        db.session.add(new_assignment)
        db.session.commit()  # Commit zodat new_assignment.id beschikbaar is

        # Verwerk dynamische items
        item_types = request.form.getlist('item_type[]')
        item_merks = request.form.getlist('item_merk[]')
        item_artikelomschrijvingen = request.form.getlist('item_artikelomschrijving[]')
        item_artikelnummers = request.form.getlist('item_artikelnummer[]')
        item_prijzen = request.form.getlist('item_prijs[]')
        item_kleuren = request.form.getlist('item_kleur_overall[]')
        item_specs = request.form.getlist('item_specs[]')
        item_files = request.files.getlist('item_file[]')
        
        for i in range(len(item_types)):
            item_filename = None
            if i < len(item_files):
                file_field = item_files[i]
                if file_field and allowed_file(file_field.filename):
                    item_filename = secure_filename(file_field.filename)
                    file_field.save(os.path.join(app.config['UPLOAD_FOLDER'], item_filename))
            specs = item_specs[i] if i < len(item_specs) else "[]"
            new_item = AssignmentItem(
                assignment_id=new_assignment.id,
                item_type=item_types[i],
                merk=item_merks[i],
                artikel_omschrijving=item_artikelomschrijvingen[i],
                artikelnummer=item_artikelnummers[i] if i < len(item_artikelnummers) else "",
                prijs=item_prijzen[i] if i < len(item_prijzen) else "",
                kleur=item_kleuren[i] if i < len(item_kleuren) else "",
                file=item_filename,
                specs=specs
            )
            db.session.add(new_item)
        
        db.session.commit()
        flash('Opdracht en alle items succesvol toegevoegd!', 'success')
        return redirect(url_for('list_assignments'))
    return render_template('add_assignment.html', customers=customers, error=error)

@app.route('/assignments')
def list_assignments():
    status_filter = request.args.get('status')
    deadline_filter = request.args.get('deadline')
    query = Assignment.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if deadline_filter:
        try:
            deadline_dt = datetime.strptime(deadline_filter, '%Y-%m-%d').date()
            query = query.filter(Assignment.deadline == deadline_dt)
        except ValueError:
            pass

    assignments = query.all()
    return render_template('assignments.html', assignments=assignments)

@app.route('/edit_assignment/<int:id>', methods=['GET', 'POST'])
def edit_assignment(id):
    assignment = Assignment.query.get_or_404(id)
    customers = Customer.query.all()
    
    if request.method == 'POST':
        assignment.customer_id = request.form.get('customer_id')
        assignment.title = request.form.get('title') or assignment.title
        assignment.description = request.form.get('description') or assignment.description
        assignment.status = request.form.get('status')
        
        deadline_str = request.form.get('deadline')
        if deadline_str:
            assignment.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        else:
            assignment.deadline = None
        
        assignment.opmerkingen = request.form.get('opmerkingen')
        assignment.status_opdracht = request.form.get('status_opdracht')
        
        file = request.files.get('file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            assignment.file = filename

        # Eerst alle bestaande items verwijderen
        for item in assignment.items:
            db.session.delete(item)
        db.session.commit()
        
        # Lees de dynamische items en de verborgen inputs in
        item_types = request.form.getlist('item_type[]')
        item_merks = request.form.getlist('item_merk[]')
        item_artikelomschrijvingen = request.form.getlist('item_artikelomschrijving[]')
        item_artikelnummers = request.form.getlist('item_artikelnummer[]')
        item_prijzen = request.form.getlist('item_prijs[]')
        item_kleuren = request.form.getlist('item_kleur_overall[]')
        item_specs = request.form.getlist('item_specs[]')
        item_files = request.files.getlist('item_file[]')
        existing_files = request.form.getlist('existing_item_file[]')
        
        for i in range(len(item_types)):
            item_filename = None
            # Controleer of er een nieuw bestand is geüpload
            if i < len(item_files):
                file_field = item_files[i]
                if file_field and allowed_file(file_field.filename):
                    item_filename = secure_filename(file_field.filename)
                    file_field.save(os.path.join(app.config['UPLOAD_FOLDER'], item_filename))
            # Als er geen nieuw bestand is, gebruik dan de bestaande bestandsnaam uit de verborgen input
            if not item_filename and existing_files and i < len(existing_files) and existing_files[i]:
                item_filename = existing_files[i]
            specs = item_specs[i] if i < len(item_specs) else "[]"
            new_item = AssignmentItem(
                assignment_id=assignment.id,
                item_type=item_types[i],
                merk=item_merks[i],
                artikel_omschrijving=item_artikelomschrijvingen[i],
                artikelnummer=item_artikelnummers[i] if i < len(item_artikelnummers) else "",
                prijs=item_prijzen[i] if i < len(item_prijzen) else "",
                file=item_filename,
                kleur=item_kleuren[i] if i < len(item_kleuren) else "",
                specs=specs
            )
            db.session.add(new_item)
        
        db.session.commit()
        flash('Opdracht en alle items succesvol bijgewerkt!', 'success')
        return redirect(url_for('list_assignments'))
    
    # Bouw de JSON-string voor de dynamische items, inclusief het bestandveld
    items_data = json.dumps([
        {
            'type': item.item_type,
            'merk': item.merk,
            'artikelOmschrijving': item.artikel_omschrijving,
            'artikelnummer': item.artikelnummer,
            'prijs': item.prijs,
            'kleur': item.kleur,
            'specs': item.specs,
            'file': item.file  # Bestandsnaam van de geüploade afbeelding/bestand
        }
        for item in assignment.items if item.item_type != "[ITEM TYPE]"
    ])
    
    return render_template('add_assignment.html', customers=customers, assignment=assignment, items_data=items_data)

@app.route('/delete_assignment/<int:id>', methods=['POST'])
def delete_assignment(id):
    assignment = Assignment.query.get_or_404(id)
    db.session.delete(assignment)
    db.session.commit()
    flash('Opdracht succesvol verwijderd!', 'success')
    return redirect(url_for('list_assignments'))

# ---------------------
# Factuurgegevens
# ---------------------

@app.route('/billing_infos')
def list_billing_infos():
    billing_infos = BillingInfo.query.all()
    return render_template('billing_infos.html', billing_infos=billing_infos)

@app.route('/add_billing_info', methods=['GET', 'POST'])
def add_billing_info():
    if request.method == 'POST':
        new_bi = BillingInfo(
            name=request.form.get('name'),
            address=request.form.get('address'),
            postcode=request.form.get('postcode'),
            housenumber=request.form.get('housenumber'),
            phone=request.form.get('phone'),
            companyname=request.form.get('companyname'),
            email=request.form.get('email')
        )
        db.session.add(new_bi)
        db.session.commit()
        return redirect(url_for('list_billing_infos'))
    return render_template('add_billing_info.html')

@app.route('/save_billing_info', methods=['POST'])
def save_billing_info():
    data = request.get_json()
    name = data.get('name')
    companyname = data.get('companyname')
    address = data.get('address')
    postcode = data.get('postcode')
    housenumber = data.get('housenumber')
    phone = data.get('phone')
    email = data.get('email')
    
    existing = BillingInfo.query.filter_by(
        name=name, companyname=companyname, address=address,
        postcode=postcode, housenumber=housenumber, phone=phone, email=email
    ).first()
    if existing:
        return {"status": "exists", "message": "Factuuradres bestaat al."}
    
    new_bi = BillingInfo(
        name=name,
        companyname=companyname,
        address=address,
        postcode=postcode,
        housenumber=housenumber,
        phone=phone,
        email=email
    )
    db.session.add(new_bi)
    db.session.commit()
    key = f"{name} - {companyname} - {address}"
    return {"status": "success", "message": "Factuuradres succesvol opgeslagen.", "key": key, "billing_info": {
        "name": name,
        "companyname": companyname,
        "address": address,
        "postcode": postcode,
        "housenumber": housenumber,
        "phone": phone,
        "email": email
    }}

# Nieuwe route: zoek in de klanten (dynamisch via AJAX)
@app.route('/search_customers')
def search_customers():
    query = request.args.get('q', '')
    results = Customer.query.filter(
        Customer.name.ilike(f"%{query}%") | Customer.email.ilike(f"%{query}%")
    ).all()
    customers_data = []
    for customer in results:
        customers_data.append({
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "telefoon": customer.telefoon,
            "billing": {
                "name": customer.billing_info.name if customer.billing_info else "",
                "companyname": customer.billing_info.companyname if customer.billing_info else "",
                "address": customer.billing_info.address if customer.billing_info else "",
                "postcode": customer.billing_info.postcode if customer.billing_info else "",
                "housenumber": customer.billing_info.housenumber if customer.billing_info else "",
                "phone": customer.billing_info.phone if customer.billing_info else "",
                "email": customer.billing_info.email if customer.billing_info else ""
            },
            "vereniging": customer.vereniging,
            "referentie": customer.referentie
        })
    return jsonify(customers_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
