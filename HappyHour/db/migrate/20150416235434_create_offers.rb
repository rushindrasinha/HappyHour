class CreateOffers < ActiveRecord::Migration
  def change
    create_table :offers do |t|
      t.text :description
      t.string :item
      t.float :price
      t.references :bar, index: true

      t.timestamps null: false
    end
    add_foreign_key :offers, :bars
  end
end
