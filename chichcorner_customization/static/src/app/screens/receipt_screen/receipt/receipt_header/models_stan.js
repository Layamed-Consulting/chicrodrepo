/** @odoo-module */
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);
        this.stan = this.stan || null;
        this.identite_number = this.identite_number || null;
        this.cheque_number = this.cheque_number || null;
        this.banque = this.banque || null;
        this.cheque_date = this.cheque_date || null;
        //virement part
        this.vir_number = this.vir_number || null;
        this.num_client = this.num_client || null;
        this.vir_montant = this.vir_montant || null;
        this.ref_cmd = this.ref_cmd || null;
        this.date_commande = this.date_commande || null;
    },
    init_from_JSON(json) {
        this.set_stan(json.stan);
        this.set_identite_number(json.identite_number);
        this.set_cheque_number(json.cheque_number);
        this.set_banque_name(json.banque);
        this.set_cheque_date(json.cheque_date);
        //virement part
        this.set_vir_number(json.vir_number);
        this.set_num_client(json.num_client);
        this.set_vir_montant(json.vir_montant);
        this.set_ref_cmd(json.ref_cmd);
        this.set_date_commande(json.date_commande);

        super.init_from_JSON(...arguments);
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        if (json) {
            json.stan = this.get_stan();
            json.identite_number = this.get_identite_number();
            json.cheque_number = this.get_cheque_number();
            json.banque = this.get_banque_name();
            json.cheque_date = this.get_cheque_date();
            //virement part
            json.vir_number = this.get_vir_number();
            json.num_client = this.get_num_client();
            json.vir_montant = this.get_vir_montant();
            json.ref_cmd = this.get_ref_cmd();
            json.date_commande = this.get_date_commande();
        }
        return json;
    },
    set_stan(stan) {
        this.stan = stan;
    },
    get_stan() {
        return this.stan;
    },
    set_identite_number(identite_number) {
        this.identite_number = identite_number;
    },
    set_cheque_date(cheque_date) {
        this.cheque_date = cheque_date;
    },
     get_cheque_date() {
        return this.cheque_date;
    },

    get_identite_number() {
        return this.identite_number;
    },

    set_cheque_number(cheque_number) {
        this.cheque_number = cheque_number;
    },

    get_cheque_number() {
        return this.cheque_number;
    },

    set_banque_name(banque) {
        this.banque = banque;
    },

    get_banque_name() {
        return this.banque;
    },
    //virement part
    set_vir_number(vir_number) {
        this.vir_number = vir_number;
    },

    get_vir_number() {
        return this.vir_number;
    },

    set_num_client(num_client) {
        this.num_client = num_client;
    },

    get_num_client() {
        return this.num_client;
    },

    set_vir_montant(vir_montant) {
        this.vir_montant = vir_montant;
    },

    get_vir_montant() {
        return this.vir_montant;
    },

    set_ref_cmd(ref_cmd) {
        this.ref_cmd = ref_cmd;
    },

    get_ref_cmd() {
        return this.ref_cmd;
    },
    set_date_commande(date_commande) {
        this.date_commande = date_commande;
    },
    get_date_commande() {
        return this.date_commande;
    },
});
